import { useCallback, useEffect, useRef, useState } from "react";

import "./VideoPlayer.css";

import VideoPlayerCore, { useVideoPlayer } from "./core/VideoPlayerCore";
import { VIDEO_SKINS } from "./core/videoPlayerTypes";
import ArticleVideoSkin from "./skins/ArticleVideoSkin";
import ChatVideoSkin from "./skins/ChatVideoSkin";
import MomentsVideoSkin from "./skins/MomentsVideoSkin";
import PageVideoSkin from "./skins/PageVideoSkin";
import PostVideoSkin from "./skins/PostVideoSkin";


const SKIN_COMPONENTS = {
    [VIDEO_SKINS.page]: PageVideoSkin,
    [VIDEO_SKINS.article]: ArticleVideoSkin,
    [VIDEO_SKINS.post]: PostVideoSkin,
    [VIDEO_SKINS.chat]: ChatVideoSkin,
    [VIDEO_SKINS.moments]: MomentsVideoSkin,
};

function VideoPlayerFrame({ skin }) {
    const {
        videoRef,
        playerRef,
        selectedSource,
        state,
        commands,
        posterUrl,
        title,
        preload,
        autoPlay,
    } = useVideoPlayer();
    const Skin = SKIN_COMPONENTS[skin] || ArticleVideoSkin;
    const [areControlsVisible, setAreControlsVisible] = useState(false);
    const hideControlsTimeoutRef = useRef(null);

    const clearHideControlsTimeout = useCallback(() => {
        if (hideControlsTimeoutRef.current) {
            clearTimeout(hideControlsTimeoutRef.current);
            hideControlsTimeoutRef.current = null;
        }
    }, []);

    const markControlsActivity = useCallback(() => {
        setAreControlsVisible(true);

        if (!state.isFullscreen) {
            return;
        }

        clearHideControlsTimeout();
        hideControlsTimeoutRef.current = setTimeout(() => {
            setAreControlsVisible(false);
        }, 3000);
    }, [clearHideControlsTimeout, state.isFullscreen]);

    useEffect(() => {
        if (state.isFullscreen) {
            markControlsActivity();
            return clearHideControlsTimeout;
        }

        clearHideControlsTimeout();
        setAreControlsVisible(false);
        return clearHideControlsTimeout;
    }, [clearHideControlsTimeout, markControlsActivity, state.isFullscreen]);

    useEffect(() => clearHideControlsTimeout, [clearHideControlsTimeout]);

    return (
        <div
            ref={playerRef}
            className={`video-player ${skin} ${state.isFullscreen ? "fullscreen" : ""} ${areControlsVisible ? "controls-visible" : ""}`}
            tabIndex="0"
            aria-label={title || "Video player"}
            onMouseMove={markControlsActivity}
            onPointerMove={markControlsActivity}
            onPointerDownCapture={markControlsActivity}
            onTouchStart={markControlsActivity}
            onKeyDown={markControlsActivity}
        >
            <div className="video-player-frame">
                {selectedSource ? (
                    <video
                        ref={videoRef}
                        src={selectedSource.src}
                        poster={posterUrl || undefined}
                        preload={preload}
                        autoPlay={autoPlay}
                        muted={state.muted}
                        playsInline
                        controls={false}
                        onClick={commands.togglePlay}
                    />
                ) : (
                    <div className="video-player-empty">Video source is unavailable.</div>
                )}

                {state.isLoading && state.hasSource && (
                    <div className="video-player-overlay">
                        <span className="video-player-spinner" />
                    </div>
                )}

                {state.isBuffering && !state.isLoading && !state.error && (
                    <div className="video-player-overlay passive">
                        <span className="video-player-spinner" />
                    </div>
                )}

                {state.error && (
                    <div className="video-player-overlay error">
                        <span>{state.error}</span>
                    </div>
                )}

                <div className="video-player-controls-layer" onClick={(event) => event.stopPropagation()}>
                    <Skin />
                </div>
            </div>
        </div>
    );
}

function VideoPlayer(props) {
    const {
        skin = VIDEO_SKINS.article,
        sources = [],
        initialQualityId,
        initialTimeSeconds,
        posterUrl,
        title,
        chapters,
        autoPlay,
        muted,
        preload,
        checkpoints,
        onPlay,
        onPause,
        onEnded,
        onTimeUpdate,
        onProgressCheckpoint,
        onQualityChange,
        onError,
    } = props;

    return (
        <VideoPlayerCore
            sources={sources}
            initialQualityId={initialQualityId}
            initialTimeSeconds={initialTimeSeconds}
            posterUrl={posterUrl}
            title={title}
            chapters={chapters}
            autoPlay={autoPlay}
            muted={muted}
            preload={preload}
            checkpoints={checkpoints}
            onPlay={onPlay}
            onPause={onPause}
            onEnded={onEnded}
            onTimeUpdate={onTimeUpdate}
            onProgressCheckpoint={onProgressCheckpoint}
            onQualityChange={onQualityChange}
            onError={onError}
        >
            <VideoPlayerFrame skin={skin} />
        </VideoPlayerCore>
    );
}

export default VideoPlayer;
