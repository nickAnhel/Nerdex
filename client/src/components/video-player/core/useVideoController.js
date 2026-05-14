import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import useProgressCheckpoints from "./useProgressCheckpoints";
import { DEFAULT_VOLUME } from "./videoPlayerTypes";


function getBufferedEnd(video) {
    if (!video?.buffered?.length) {
        return 0;
    }

    return video.buffered.end(video.buffered.length - 1);
}

export default function useVideoController({
    sources,
    initialQualityId,
    initialTimeSeconds,
    autoPlay = false,
    muted = false,
    checkpoints,
    onPlay,
    onPause,
    onEnded,
    onTimeUpdate,
    onProgressCheckpoint,
    onQualityChange,
    onError,
}) {
    const videoRef = useRef(null);
    const playerRef = useRef(null);
    const pendingQualitySwitchRef = useRef(null);
    const initialSeekAppliedRef = useRef(false);
    const previousAutoPlayRef = useRef(autoPlay);
    const [selectedQualityId, setSelectedQualityId] = useState(
        initialQualityId || sources[0]?.id || ""
    );
    const [isPlaying, setIsPlaying] = useState(false);
    const [isLoading, setIsLoading] = useState(Boolean(sources.length));
    const [isBuffering, setIsBuffering] = useState(false);
    const [error, setError] = useState("");
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [bufferedEnd, setBufferedEnd] = useState(0);
    const [volume, setVolumeState] = useState(DEFAULT_VOLUME);
    const [isMuted, setMutedState] = useState(Boolean(muted));
    const [playbackRate, setPlaybackRateState] = useState(1);
    const [isFullscreen, setIsFullscreen] = useState(false);

    const selectedSource = useMemo(() => (
        sources.find((source) => source.id === selectedQualityId) || sources[0] || null
    ), [selectedQualityId, sources]);

    const buildPayload = useCallback((overrides = {}) => ({
        currentTime,
        duration,
        qualityId: selectedSource?.id || selectedQualityId,
        playbackRate,
        volume,
        muted: isMuted,
        ...overrides,
    }), [currentTime, duration, isMuted, playbackRate, selectedQualityId, selectedSource, volume]);

    const play = useCallback(async () => {
        const video = videoRef.current;
        if (!video || !selectedSource) {
            return;
        }

        try {
            setError("");
            await video.play();
        } catch (playError) {
            setIsPlaying(false);
            setError("Unable to start video playback.");
            onError?.(buildPayload({
                error: playError,
                mediaErrorCode: video.error?.code || null,
            }));
        }
    }, [buildPayload, onError, selectedSource]);

    const pause = useCallback(() => {
        videoRef.current?.pause();
    }, []);

    const togglePlay = useCallback(() => {
        if (videoRef.current?.paused) {
            play();
            return;
        }
        pause();
    }, [pause, play]);

    const seekTo = useCallback((nextTime) => {
        const video = videoRef.current;
        const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : video?.duration || 0;
        const boundedTime = Math.max(0, Math.min(Number(nextTime) || 0, safeDuration || Number(nextTime) || 0));

        setCurrentTime(boundedTime);
        if (video) {
            video.currentTime = boundedTime;
        }
    }, [duration]);

    const seekBy = useCallback((deltaSeconds) => {
        const video = videoRef.current;
        seekTo((video?.currentTime || currentTime) + deltaSeconds);
    }, [currentTime, seekTo]);

    const setVolume = useCallback((nextVolume) => {
        const normalizedVolume = Math.max(0, Math.min(1, Number(nextVolume) || 0));
        setVolumeState(normalizedVolume);
        if (videoRef.current) {
            videoRef.current.volume = normalizedVolume;
            videoRef.current.muted = normalizedVolume === 0 ? true : isMuted;
        }
        if (normalizedVolume > 0 && isMuted) {
            setMutedState(false);
            if (videoRef.current) {
                videoRef.current.muted = false;
            }
        }
    }, [isMuted]);

    const toggleMute = useCallback(() => {
        const nextMuted = !isMuted;
        setMutedState(nextMuted);
        if (videoRef.current) {
            videoRef.current.muted = nextMuted;
        }
    }, [isMuted]);

    const setPlaybackRate = useCallback((nextRate) => {
        const safeRate = Number(nextRate) || 1;
        setPlaybackRateState(safeRate);
        if (videoRef.current) {
            videoRef.current.playbackRate = safeRate;
        }
    }, []);

    const setQuality = useCallback((nextQualityId) => {
        const video = videoRef.current;
        if (!nextQualityId || nextQualityId === selectedQualityId) {
            return;
        }

        const nextSource = sources.find((source) => source.id === nextQualityId);
        if (!nextSource) {
            return;
        }

        pendingQualitySwitchRef.current = {
            previousQualityId: selectedQualityId,
            nextQualityId,
            currentTime: video?.currentTime || currentTime,
            shouldPlay: video ? !video.paused : isPlaying,
            volume: video?.volume ?? volume,
            muted: video?.muted ?? isMuted,
            playbackRate: video?.playbackRate || playbackRate,
        };
        setSelectedQualityId(nextQualityId);
        setIsLoading(true);
        setIsBuffering(true);
        setError("");
    }, [currentTime, isMuted, isPlaying, playbackRate, selectedQualityId, sources, volume]);

    const enterFullscreen = useCallback(async () => {
        const target = playerRef.current;
        if (!target?.requestFullscreen) {
            return;
        }
        await target.requestFullscreen();
    }, []);

    const exitFullscreen = useCallback(async () => {
        if (document.fullscreenElement && document.exitFullscreen) {
            await document.exitFullscreen();
        }
    }, []);

    const toggleFullscreen = useCallback(() => {
        if (document.fullscreenElement) {
            exitFullscreen();
        } else {
            enterFullscreen();
        }
    }, [enterFullscreen, exitFullscreen]);

    const jumpToChapter = useCallback((chapter) => {
        seekTo(chapter?.startsAtSeconds || 0);
    }, [seekTo]);

    useEffect(() => {
        if (sources.length && !sources.some((source) => source.id === selectedQualityId)) {
            setSelectedQualityId(initialQualityId || sources[0].id);
        }
        if (!sources.length) {
            setSelectedQualityId("");
            setIsLoading(false);
        }
    }, [initialQualityId, selectedQualityId, sources]);

    useEffect(() => {
        const video = videoRef.current;
        if (!video || !selectedSource) {
            previousAutoPlayRef.current = autoPlay;
            return;
        }

        if (previousAutoPlayRef.current === autoPlay) {
            return;
        }
        previousAutoPlayRef.current = autoPlay;

        if (autoPlay) {
            void play();
            return;
        }
        pause();
    }, [autoPlay, pause, play, selectedSource]);

    useEffect(() => {
        const video = videoRef.current;
        if (!video) {
            return undefined;
        }

        video.volume = volume;
        video.muted = isMuted;
        video.playbackRate = playbackRate;

        const handleLoadedMetadata = () => {
            const pendingSwitch = pendingQualitySwitchRef.current;
            setDuration(Number.isFinite(video.duration) ? video.duration : 0);
            setBufferedEnd(getBufferedEnd(video));
            setIsLoading(false);
            setIsBuffering(false);

            if (pendingSwitch) {
                video.currentTime = Math.min(pendingSwitch.currentTime, video.duration || pendingSwitch.currentTime);
                video.volume = pendingSwitch.volume;
                video.muted = pendingSwitch.muted;
                video.playbackRate = pendingSwitch.playbackRate;
                setCurrentTime(video.currentTime);
                setVolumeState(pendingSwitch.volume);
                setMutedState(pendingSwitch.muted);
                setPlaybackRateState(pendingSwitch.playbackRate);

                onQualityChange?.(buildPayload({
                    currentTime: video.currentTime,
                    duration: Number.isFinite(video.duration) ? video.duration : 0,
                    qualityId: pendingSwitch.nextQualityId,
                    previousQualityId: pendingSwitch.previousQualityId,
                    nextQualityId: pendingSwitch.nextQualityId,
                    volume: pendingSwitch.volume,
                    muted: pendingSwitch.muted,
                    playbackRate: pendingSwitch.playbackRate,
                }));

                if (pendingSwitch.shouldPlay) {
                    video.play().catch((playError) => {
                        setIsPlaying(false);
                        setError("Unable to resume video playback.");
                        onError?.(buildPayload({
                            error: playError,
                            mediaErrorCode: video.error?.code || null,
                        }));
                    });
                }
                pendingQualitySwitchRef.current = null;
            } else {
                if (!initialSeekAppliedRef.current && Number(initialTimeSeconds) > 0) {
                    const targetTime = Math.min(Number(initialTimeSeconds), video.duration || Number(initialTimeSeconds));
                    video.currentTime = targetTime;
                    setCurrentTime(targetTime);
                    initialSeekAppliedRef.current = true;
                }
                if (autoPlay) {
                    video.play().catch(() => {});
                }
            }
        };

        const handleTimeUpdate = () => {
            const nextCurrentTime = video.currentTime || 0;
            const nextDuration = Number.isFinite(video.duration) ? video.duration : duration;
            setCurrentTime(nextCurrentTime);
            setBufferedEnd(getBufferedEnd(video));
            onTimeUpdate?.(buildPayload({
                currentTime: nextCurrentTime,
                duration: nextDuration,
            }));
        };

        const handleProgress = () => setBufferedEnd(getBufferedEnd(video));
        const handleWaiting = () => setIsBuffering(true);
        const handleCanPlay = () => {
            setIsLoading(false);
            setIsBuffering(false);
        };
        const handlePlay = () => {
            setIsPlaying(true);
            onPlay?.(buildPayload({
                currentTime: video.currentTime || 0,
                duration: Number.isFinite(video.duration) ? video.duration : duration,
            }));
        };
        const handlePause = () => {
            setIsPlaying(false);
            onPause?.(buildPayload({
                currentTime: video.currentTime || 0,
                duration: Number.isFinite(video.duration) ? video.duration : duration,
            }));
        };
        const handleEnded = () => {
            setIsPlaying(false);
            onEnded?.(buildPayload({
                currentTime: video.currentTime || 0,
                duration: Number.isFinite(video.duration) ? video.duration : duration,
            }));
        };
        const handleError = () => {
            const mediaError = video.error;
            const message = "Unable to load this video.";
            setError(message);
            setIsLoading(false);
            setIsBuffering(false);
            onError?.(buildPayload({
                error: message,
                mediaErrorCode: mediaError?.code || null,
            }));
        };

        video.addEventListener("loadedmetadata", handleLoadedMetadata);
        video.addEventListener("durationchange", handleLoadedMetadata);
        video.addEventListener("timeupdate", handleTimeUpdate);
        video.addEventListener("progress", handleProgress);
        video.addEventListener("waiting", handleWaiting);
        video.addEventListener("canplay", handleCanPlay);
        video.addEventListener("playing", handleCanPlay);
        video.addEventListener("play", handlePlay);
        video.addEventListener("pause", handlePause);
        video.addEventListener("ended", handleEnded);
        video.addEventListener("error", handleError);

        return () => {
            video.removeEventListener("loadedmetadata", handleLoadedMetadata);
            video.removeEventListener("durationchange", handleLoadedMetadata);
            video.removeEventListener("timeupdate", handleTimeUpdate);
            video.removeEventListener("progress", handleProgress);
            video.removeEventListener("waiting", handleWaiting);
            video.removeEventListener("canplay", handleCanPlay);
            video.removeEventListener("playing", handleCanPlay);
            video.removeEventListener("play", handlePlay);
            video.removeEventListener("pause", handlePause);
            video.removeEventListener("ended", handleEnded);
            video.removeEventListener("error", handleError);
        };
    }, [
        autoPlay,
        buildPayload,
        duration,
        isMuted,
        initialTimeSeconds,
        onEnded,
        onError,
        onPause,
        onPlay,
        onQualityChange,
        onTimeUpdate,
        playbackRate,
        selectedSource,
        volume,
    ]);

    useEffect(() => {
        const handleFullscreenChange = () => {
            setIsFullscreen(document.fullscreenElement === playerRef.current);
        };

        document.addEventListener("fullscreenchange", handleFullscreenChange);
        return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
    }, []);

    useProgressCheckpoints({
        currentTime,
        duration,
        checkpoints,
        selectedQualityId,
        playbackRate,
        volume,
        muted: isMuted,
        onProgressCheckpoint,
    });

    const commands = useMemo(() => ({
        play,
        pause,
        togglePlay,
        seekTo,
        seekBy,
        setVolume,
        toggleMute,
        setPlaybackRate,
        setQuality,
        enterFullscreen,
        exitFullscreen,
        toggleFullscreen,
        jumpToChapter,
    }), [
        enterFullscreen,
        exitFullscreen,
        jumpToChapter,
        pause,
        play,
        seekBy,
        seekTo,
        setPlaybackRate,
        setQuality,
        setVolume,
        toggleFullscreen,
        toggleMute,
        togglePlay,
    ]);

    return {
        videoRef,
        playerRef,
        selectedSource,
        state: {
            isPlaying,
            isLoading,
            isBuffering,
            error,
            currentTime,
            duration,
            bufferedEnd,
            volume,
            muted: isMuted,
            playbackRate,
            selectedQualityId: selectedSource?.id || selectedQualityId,
            isFullscreen,
            hasSource: Boolean(selectedSource),
        },
        commands,
    };
}
