from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware 
import cv2
import numpy as np
from PIL import Image
import io
import base64 

app = FastAPI()

origins = [
    "https://forest-agent.vercel.app/",
    # "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], 
)

def pil_image_to_base64(pil_image, format="PNG"):
    buffered = io.BytesIO()
    pil_image.save(buffered, format=format)
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/{format.lower()};base64,{img_str}"

def detect_forest_area(image_array):
    hsv_image = cv2.cvtColor(image_array, cv2.COLOR_RGB2HSV)
    lower_green = np.array([35, 40, 40])
    upper_green = np.array([90, 255, 255])
    mask = cv2.inRange(hsv_image, lower_green, upper_green)
    return mask

def align_images_orb(img_ref_np, img_to_align_np, min_matches=30, n_features=2000):
    img_ref_gray = cv2.cvtColor(img_ref_np, cv2.COLOR_RGB2GRAY)
    img_to_align_gray = cv2.cvtColor(img_to_align_np, cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(nfeatures=n_features)
    kp_ref, des_ref = orb.detectAndCompute(img_ref_gray, None)
    kp_to_align, des_to_align = orb.detectAndCompute(img_to_align_gray, None)

    if des_ref is None or des_to_align is None:
        return img_ref_np, img_to_align_np, False, "Could not compute descriptors."

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des_to_align, des_ref)
    matches = sorted(matches, key=lambda x: x.distance)

    if len(matches) >= min_matches:
        src_pts = np.float32([kp_to_align[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp_ref[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        H, mask_homography = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if H is not None:
            h_ref, w_ref = img_ref_np.shape[:2]
            img_aligned_np = cv2.warpPerspective(img_to_align_np, H, (w_ref, h_ref))
            return img_ref_np, img_aligned_np, True, "Feature-based alignment successful."
        else:
            return img_ref_np, img_to_align_np, False, "Homography estimation failed."
    else:
        return img_ref_np, img_to_align_np, False, f"Not enough matches found ({len(matches)}/{min_matches})."


@app.post("/api/analyze-forest")
async def analyze_forest_cover(
    before_image_file: UploadFile = File(...),
    after_image_file: UploadFile = File(...)
):
    try:
        contents_before = await before_image_file.read()
        contents_after = await after_image_file.read()

        image_before_pil = Image.open(io.BytesIO(contents_before)).convert('RGB')
        image_after_pil = Image.open(io.BytesIO(contents_after)).convert('RGB')

        image_before_np_orig = np.array(image_before_pil)
        image_after_np_orig = np.array(image_after_pil)
        
        image_before_np = image_before_np_orig.copy()
        image_after_np = image_after_np_orig.copy()
        
        alignment_message = "Images have the same dimensions."
        alignment_status = "N/A"

        if image_before_np.shape[:2] != image_after_np.shape[:2]:
            alignment_status = "Attempting alignment..."
            
            ref_img_aligned, sec_img_aligned, success, orb_message = align_images_orb(
                image_before_np_orig, image_after_np_orig
            )
            
            if success:
                image_before_np = ref_img_aligned
                image_after_np = sec_img_aligned
                alignment_message = orb_message
                alignment_status = "ORB Alignment Successful"
            else:
                alignment_status = f"ORB Alignment Failed: {orb_message}. Falling back to resize."
                h_before, w_before = image_before_np_orig.shape[:2]
                h_after, w_after = image_after_np_orig.shape[:2]
                area_before = h_before * w_before
                area_after = h_after * w_after

                if area_before < area_after:
                    target_dims = (w_before, h_before)
                    image_after_np = cv2.resize(image_after_np_orig, target_dims, interpolation=cv2.INTER_AREA)
                    image_before_np = image_before_np_orig.copy()
                    alignment_message = f"'After' image resized to {w_before}x{h_before}."
                else: 
                    target_dims = (w_after, h_after)
                    image_before_np = cv2.resize(image_before_np_orig, target_dims, interpolation=cv2.INTER_AREA)
                    image_after_np = image_after_np_orig.copy()
                    alignment_message = f"'Before' image resized to {w_after}x{h_after}."
        
        mask_before_np = detect_forest_area(image_before_np)
        mask_after_np = detect_forest_area(image_after_np)

        total_pixels = image_before_np.shape[0] * image_before_np.shape[1]
        forest_pixels_before = np.sum(mask_before_np == 255)
        forest_pixels_after = np.sum(mask_after_np == 255)
        percentage_before = (forest_pixels_before / total_pixels) * 100 if total_pixels > 0 else 0
        percentage_after = (forest_pixels_after / total_pixels) * 100 if total_pixels > 0 else 0
        change_percentage = percentage_after - percentage_before

        loss_mask_np = cv2.subtract(mask_before_np, mask_after_np)
        gain_mask_np = cv2.subtract(mask_after_np, mask_before_np)
        pixels_lost = np.sum(loss_mask_np == 255)
        pixels_gained = np.sum(gain_mask_np == 255)
        percentage_loss = (pixels_lost / total_pixels) * 100 if total_pixels > 0 else 0
        percentage_gain = (pixels_gained / total_pixels) * 100 if total_pixels > 0 else 0

        change_visualization_np = image_after_np.copy()
        if len(change_visualization_np.shape) == 2 or change_visualization_np.shape[2] == 1:
             change_visualization_np = cv2.cvtColor(change_visualization_np, cv2.COLOR_GRAY2RGB)
        change_visualization_np[loss_mask_np == 255] = [255, 0, 0]
        change_visualization_np[gain_mask_np == 255] = [0, 255, 0]

       
        processed_before_pil = Image.fromarray(image_before_np)
        processed_after_pil = Image.fromarray(image_after_np)
        
        mask_before_pil = Image.fromarray(mask_before_np)
        mask_after_pil = Image.fromarray(mask_after_np)
        change_visualization_pil = Image.fromarray(change_visualization_np)

        return {
            "message": "Analysis successful",
            "alignment_status": alignment_status,
            "alignment_message": alignment_message,
            "processed_image_before": pil_image_to_base64(processed_before_pil),
            "processed_image_after": pil_image_to_base64(processed_after_pil),
            "mask_before": pil_image_to_base64(mask_before_pil),
            "mask_after": pil_image_to_base64(mask_after_pil),
            "change_visualization": pil_image_to_base64(change_visualization_pil),
            "stats": {
                "total_pixels": total_pixels,
                "forest_pixels_before": int(forest_pixels_before),
                "forest_pixels_after": int(forest_pixels_after),
                "percentage_before": round(percentage_before, 2),
                "percentage_after": round(percentage_after, 2),
                "change_percentage": round(change_percentage, 2),
                "pixels_lost": int(pixels_lost),
                "pixels_gained": int(pixels_gained),
                "percentage_loss": round(percentage_loss, 2),
                "percentage_gain": round(percentage_gain, 2),
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))