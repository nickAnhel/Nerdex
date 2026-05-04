import { createContext, useContext, useMemo } from "react";

import useVideoController from "./useVideoController";
import useVideoKeyboardShortcuts from "./useVideoKeyboardShortcuts";
import { normalizeChapters, normalizeSources } from "./videoPlayerTypes";


const VideoPlayerContext = createContext(null);

export function useVideoPlayer() {
    const context = useContext(VideoPlayerContext);
    if (!context) {
        throw new Error("useVideoPlayer must be used inside VideoPlayerCore.");
    }
    return context;
}

function VideoPlayerCore({
    sources = [],
    initialQualityId,
    posterUrl,
    title,
    chapters = [],
    autoPlay = false,
    muted = false,
    preload = "metadata",
    checkpoints,
    onPlay,
    onPause,
    onEnded,
    onTimeUpdate,
    onProgressCheckpoint,
    onQualityChange,
    onError,
    children,
}) {
    const normalizedSources = useMemo(() => normalizeSources(sources), [sources]);
    const normalizedChapters = useMemo(() => normalizeChapters(chapters), [chapters]);
    const controller = useVideoController({
        sources: normalizedSources,
        initialQualityId,
        autoPlay,
        muted,
        checkpoints,
        onPlay,
        onPause,
        onEnded,
        onTimeUpdate,
        onProgressCheckpoint,
        onQualityChange,
        onError,
    });

    useVideoKeyboardShortcuts(controller.playerRef, controller.commands);

    const value = useMemo(() => ({
        ...controller,
        sources: normalizedSources,
        chapters: normalizedChapters,
        posterUrl,
        title,
        preload,
        autoPlay,
    }), [autoPlay, controller, normalizedChapters, normalizedSources, posterUrl, preload, title]);

    return (
        <VideoPlayerContext.Provider value={value}>
            {children}
        </VideoPlayerContext.Provider>
    );
}

export default VideoPlayerCore;
