import React, { useEffect, useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
    const [video, setVideo] = useState(null);
    const [videoURL, setVideoURL] = useState('');
    const [outputURL, setOutputURL] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [progress, setProgress] = useState(0);
    const [progressText, setProgressText] = useState('');

    useEffect(() => {
        return () => {
            if (videoURL) URL.revokeObjectURL(videoURL);
            if (outputURL) URL.revokeObjectURL(outputURL);
        };
    }, [videoURL, outputURL]);

    const handleVideoChange = (e) => {
        const file = e.target.files[0];

        if (!file) return;

        if (videoURL) URL.revokeObjectURL(videoURL);
        if (outputURL) URL.revokeObjectURL(outputURL);

        setVideo(file);
        setVideoURL(URL.createObjectURL(file));
        setOutputURL('');
        setError('');
        setProgress(0);
        setProgressText('');
    };

    const uploadVideo = async () => {
        if (!video || loading) {
            setError('Select a video file before starting detection.');
            return;
        }

        const formData = new FormData();
        formData.append('video', video);

        try {
            setLoading(true);
            setError('');
            setProgress(0);
            setProgressText('Queued for processing');

            const uploadResponse = await axios.post(
                'http://127.0.0.1:5000/upload',
                formData,
                {
                    headers: {
                        Accept: 'application/json',
                    },
                }
            );

            const { job_id: jobId } = uploadResponse.data;

            if (!jobId) {
                throw new Error('Server did not return a processing job.');
            }

            let done = false;

            while (!done) {
                await wait(700);

                const progressResponse = await axios.get(
                    `http://127.0.0.1:5000/progress/${jobId}`
                );

                const job = progressResponse.data;
                const nextProgress = Number(job.progress || 0);

                setProgress(nextProgress);

                if (job.total_frames > 0) {
                    setProgressText(
                        `${job.processed_frames} of ${job.total_frames} frames analyzed`
                    );
                } else {
                    setProgressText('Preparing video frames');
                }

                if (job.status === 'error') {
                    throw new Error(job.error || 'Processing failed.');
                }

                if (job.status === 'done') {
                    done = true;
                }
            }

            const response = await axios.get(
                `http://127.0.0.1:5000/result/${jobId}`,
                { responseType: 'blob' }
            );

            if (outputURL) URL.revokeObjectURL(outputURL);

            const contentType = response.headers['content-type'] || 'video/webm';
            const blob = new Blob([response.data], { type: contentType });
            setOutputURL(URL.createObjectURL(blob));
            setProgress(100);
            setProgressText('Detection complete');
        } catch (uploadError) {
            console.error(uploadError);
            setError(uploadError.message || 'Processing failed. Check that the Flask server is running and try another video.');
            setProgress(0);
            setProgressText('');
        } finally {
            setLoading(false);
        }
    };

    const fileSize = video ? `${(video.size / (1024 * 1024)).toFixed(1)} MB` : 'No file';

    return (
        <main className="app">
            <section className="workspace">
                <header className="topbar">
                    <div className="brand">
                        <div className="brandMark" aria-hidden="true">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                                <path d="M12 3l7 4v5c0 4.5-2.9 7.7-7 9-4.1-1.3-7-4.5-7-9V7l7-4z" stroke="currentColor" strokeWidth="2" />
                                <path d="M9 13l2 2 4-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                        </div>
                        <div>
                            <h1>Crack Detection</h1>
                            <p>Concrete surface inspection console</p>
                        </div>
                    </div>

                    <div className="serverBadge">
                        <span></span>
                        Flask API: 127.0.0.1:5000
                    </div>
                </header>

                <section className="hero">
                    <div className="heroCopy">
                        <p className="eyebrow">Video analysis</p>
                        <h2>Inspect footage, detect crack regions, and export the overlay video.</h2>
                        <p>
                            Upload a camera clip and the model returns a processed video with color-coded crack severity.
                        </p>
                    </div>

                    <div className="settingsPanel">
                        <div>
                            <span>Threshold</span>
                            <strong>0.80</strong>
                        </div>
                        <div>
                            <span>Min width</span>
                            <strong>0.08 mm</strong>
                        </div>
                        <div>
                            <span>Smoothing</span>
                            <strong>5 frames</strong>
                        </div>
                    </div>
                </section>

                <section className="controlGrid">
                    <div className="panel uploadPanel">
                        <label className="dropZone">
                            <input type="file" accept="video/*" onChange={handleVideoChange} />
                            <span className="uploadIcon" aria-hidden="true">
                                <svg width="28" height="28" viewBox="0 0 24 24" fill="none">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                                    <path d="M17 8l-5-5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                                    <path d="M12 3v12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                                </svg>
                            </span>
                            <span>
                                <strong>{video ? video.name : 'Choose inspection footage'}</strong>
                                <small>{video ? `${fileSize} selected` : 'MP4, MOV, AVI, or camera video'}</small>
                            </span>
                        </label>

                        {error && <div className="notice error">{error}</div>}

                        {loading && (
                            <div className="notice processing">
                                <span className="spinner"></span>
                                <span className="progressContent">
                                    <strong>Processing video</strong>
                                    <small>{progressText || 'The model is analyzing each frame.'}</small>
                                    <span className="progressTrack" aria-label="Model progress">
                                        <span style={{ width: `${progress}%` }}></span>
                                    </span>
                                    <small>{progress}% complete</small>
                                </span>
                            </div>
                        )}

                        <button className="primaryButton" type="button" onClick={uploadVideo} disabled={loading}>
                            {loading ? 'Analyzing...' : 'Start Detection'}
                        </button>
                    </div>

                    <aside className="panel legendPanel">
                        <h3>Severity legend</h3>
                        <div className="legendRow"><span className="minor"></span>Minor under 0.5 mm</div>
                        <div className="legendRow"><span className="moderate"></span>Moderate 0.5 to 1 mm</div>
                        <div className="legendRow"><span className="severe"></span>Severe 1 mm and above</div>
                    </aside>
                </section>

                <section className="videoGrid">
                    <VideoCard title="Input Video" emptyText="Selected footage preview appears here." url={videoURL} />
                    <VideoCard
                        title="Detected Output"
                        emptyText="Processed overlay will appear after detection."
                        url={outputURL}
                        download
                    />
                </section>
            </section>
        </main>
    );
}

function wait(ms) {
    return new Promise((resolve) => {
        setTimeout(resolve, ms);
    });
}

function VideoCard({ title, emptyText, url, download = false }) {
    return (
        <article className="panel videoCard">
            <div className="cardHeader">
                <h3>{title}</h3>
                {url && <span>Ready</span>}
            </div>

            {url ? (
                <>
                    <video key={url} src={url} controls className="videoPlayer" />
                    {download && (
                        <a href={url} download="crack_output.webm" className="downloadButton">
                            Download Output
                        </a>
                    )}
                </>
            ) : (
                <div className="emptyState">{emptyText}</div>
            )}
        </article>
    );
}

export default App;
