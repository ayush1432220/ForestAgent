import Head from 'next/head'; 
import { useState } from 'react';
import axios from 'axios';
import styles from '../styles/Home.module.css';

export default function HomePage() {
  const [beforeImage, setBeforeImage] = useState(null);
  const [afterImage, setAfterImage] = useState(null);
  const [beforePreview, setBeforePreview] = useState('');
  const [afterPreview, setAfterPreview] = useState('');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleBeforeImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setBeforeImage(file);
      setBeforePreview(URL.createObjectURL(file));
      setAnalysisResult(null);
      setError('');
    }
  };

  const handleAfterImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setAfterImage(file);
      setAfterPreview(URL.createObjectURL(file));
      setAnalysisResult(null);
      setError('');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!beforeImage || !afterImage) {
      setError('Please upload both "Before" and "After" images.');
      return;
    }

    setIsLoading(true);
    setError('');
    setAnalysisResult(null);

    const formData = new FormData();
    formData.append('before_image_file', beforeImage);
    formData.append('after_image_file', afterImage);

    try {
      const response = await axios.post('http://localhost:8000/api/analyze-forest', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setAnalysisResult(response.data);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'An error occurred during analysis. Check backend logs.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <Head>
        <title>Forest Cover Analyzer</title>
        <meta name="description" content="Analyze forest cover changes" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <main className={styles.main}>
        <h1 className={styles.title}>
          🌳 Forest Cover Analyzer 🌲
        </h1>

        <p className={styles.description}>
          Upload 'Before' and 'After' satellite images to analyze changes.
        </p>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.uploadSection}>
            <div>
              <h3>Before Image</h3>
              <input type="file" accept="image/jpeg, image/png" onChange={handleBeforeImageChange} />
              {beforePreview && <img src={beforePreview} alt="Before Preview" className={styles.previewImage} />}
            </div>
            <div>
              <h3>After Image</h3>
              <input type="file" accept="image/jpeg, image/png" onChange={handleAfterImageChange} />
              {afterPreview && <img src={afterPreview} alt="After Preview" className={styles.previewImage} />}
            </div>
          </div>
          <button type="submit" disabled={isLoading || !beforeImage || !afterImage} className={styles.analyzeButton}>
            {isLoading ? 'Analyzing...' : 'Analyze Forest Cover Change'}
          </button>
        </form>

        {error && <p className={styles.errorText}>{error}</p>}
        
        {isLoading && <p>Processing your images, please wait...</p>}

        {analysisResult && (
          <div className={styles.resultsSection}>
            <h2>Analysis Results</h2>
            {analysisResult.alignment_message && analysisResult.alignment_message !== "Images have the same dimensions." && (
                <p><strong>Alignment Note:</strong> {analysisResult.alignment_message}</p>
            )}

            <div className={styles.imageGrid}>
                {analysisResult.processed_image_before && (
                    <div>
                        <h4>Processed Before Image</h4>
                        <img src={analysisResult.processed_image_before} alt="Processed Before" className={styles.resultImage}/>
                    </div>
                )}
                {analysisResult.processed_image_after && (
                    <div>
                        <h4>Processed After Image</h4>
                        <img src={analysisResult.processed_image_after} alt="Processed After" className={styles.resultImage}/>
                    </div>
                )}
            </div>

            <div className={styles.imageGrid}>
                {analysisResult.mask_before && (
                    <div>
                        <h4>Forest Mask (Before)</h4>
                        <img src={analysisResult.mask_before} alt="Forest Mask Before" className={styles.resultImage}/>
                    </div>
                )}
                {analysisResult.mask_after && (
                    <div>
                        <h4>Forest Mask (After)</h4>
                        <img src={analysisResult.mask_after} alt="Forest Mask After" className={styles.resultImage}/>
                    </div>
                )}
            </div>
            
            {analysisResult.change_visualization && (
                <div style={{textAlign: 'center', margin: '20px 0'}}>
                    <h4>Change Visualization (Red: Loss, Green: Gain)</h4>
                    <img src={analysisResult.change_visualization} alt="Change Visualization" className={styles.resultImageLarge}/>
                </div>
            )}

            {analysisResult.stats && (
                <div className={styles.statsContainer}>
                    <h3>Forest Cover Statistics:</h3>
                    <p>
                        <strong>Before Image:</strong> {analysisResult.stats.forest_pixels_before?.toLocaleString()} forest pixels
                        ({analysisResult.stats.percentage_before?.toFixed(2)}%)
                    </p>
                    <p>
                        <strong>After Image:</strong> {analysisResult.stats.forest_pixels_after?.toLocaleString()} forest pixels
                        ({analysisResult.stats.percentage_after?.toFixed(2)}%)
                    </p>

                    {analysisResult.stats.change_percentage > 0.01 ? (
                        <p style={{ color: 'green', fontWeight: 'bold' }}>
                            Forest cover increased by {analysisResult.stats.change_percentage?.toFixed(2)}%.
                        </p>
                    ) : analysisResult.stats.change_percentage < -0.01 ? (
                        <p style={{ color: 'red', fontWeight: 'bold' }}>
                            Forest cover decreased by {Math.abs(analysisResult.stats.change_percentage)?.toFixed(2)}%.
                        </p>
                    ) : (
                        <p style={{ fontStyle: 'italic' }}>
                            No significant net change in forest cover detected.
                        </p>
                    )}

                    <h3>Change Details:</h3>
                    <p>
                        <strong>Area Lost (Deforestation):</strong> {analysisResult.stats.pixels_lost?.toLocaleString()} pixels
                        ({analysisResult.stats.percentage_loss?.toFixed(2)}% of total area)
                    </p>
                    <p>
                        <strong>Area Gained (Reforestation):</strong> {analysisResult.stats.pixels_gained?.toLocaleString()} pixels
                        ({analysisResult.stats.percentage_gain?.toFixed(2)}% of total area)
                    </p>
                </div>
            )}
           
          </div>
        )}
      </main>
    </div>
  );
}