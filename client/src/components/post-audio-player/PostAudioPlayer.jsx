import { useEffect, useRef, useState } from "react";

import "./PostAudioPlayer.css";

import PauseIcon from "../icons/PauseIcon";
import PlayIcon from "../icons/PlayIcon";
import VolumeIcon from "../icons/VolumeIcon";


function formatTime(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) {
        return "0:00";
    }

    const totalSeconds = Math.floor(seconds);
    const minutes = Math.floor(totalSeconds / 60);
    const remainingSeconds = totalSeconds % 60;

    return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

function getRangeStyle(value, max) {
    const safeMax = Number.isFinite(max) && max > 0 ? max : 0;
    const safeValue = Number.isFinite(value) && value > 0 ? Math.min(value, safeMax || value) : 0;
    const progress = safeMax > 0 ? (safeValue / safeMax) * 100 : 0;

    return {
        "--range-progress": `${progress}%`,
    };
}

function PostAudioPlayer({ src, durationMs = null }) {
    const audioRef = useRef(null);

    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(
        Number.isFinite(durationMs) && durationMs > 0 ? durationMs / 1000 : 0
    );
    const [volume, setVolume] = useState(0.85);
    const [isVolumeExpanded, setIsVolumeExpanded] = useState(false);

    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) {
            return undefined;
        }

        audio.volume = volume;

        const handleLoadedMetadata = () => {
            if (Number.isFinite(audio.duration) && audio.duration > 0) {
                setDuration(audio.duration);
            }
        };

        const handleTimeUpdate = () => {
            setCurrentTime(audio.currentTime || 0);
        };

        const handlePlay = () => setIsPlaying(true);
        const handlePause = () => setIsPlaying(false);

        audio.addEventListener("loadedmetadata", handleLoadedMetadata);
        audio.addEventListener("timeupdate", handleTimeUpdate);
        audio.addEventListener("play", handlePlay);
        audio.addEventListener("pause", handlePause);
        audio.addEventListener("ended", handlePause);

        return () => {
            audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
            audio.removeEventListener("timeupdate", handleTimeUpdate);
            audio.removeEventListener("play", handlePlay);
            audio.removeEventListener("pause", handlePause);
            audio.removeEventListener("ended", handlePause);
        };
    }, [volume]);

    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) {
            return;
        }

        audio.pause();
        audio.currentTime = 0;
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(Number.isFinite(durationMs) && durationMs > 0 ? durationMs / 1000 : 0);
    }, [src, durationMs]);

    const togglePlayback = async () => {
        const audio = audioRef.current;
        if (!audio) {
            return;
        }

        if (isPlaying) {
            audio.pause();
            return;
        }

        try {
            await audio.play();
        } catch (error) {
            setIsPlaying(false);
        }
    };

    const handleSeek = (event) => {
        const audio = audioRef.current;
        const nextTime = Number(event.target.value);
        setCurrentTime(nextTime);
        if (audio) {
            audio.currentTime = nextTime;
        }
    };

    const handleVolumeChange = (event) => {
        const nextVolume = Number(event.target.value);
        setVolume(nextVolume);
        if (audioRef.current) {
            audioRef.current.volume = nextVolume;
        }
    };

    return (
        <div className="post-audio-player">
            <audio ref={audioRef} src={src} preload="metadata" />

            <button
                type="button"
                className="post-audio-control primary"
                onClick={togglePlayback}
                aria-label={isPlaying ? "Pause audio" : "Play audio"}
            >
                {isPlaying ? <PauseIcon /> : <PlayIcon />}
            </button>

            <div className="post-audio-track-group">
                <input
                    className="post-audio-progress"
                    type="range"
                    min="0"
                    max={duration || 0}
                    step="0.1"
                    value={Math.min(currentTime, duration || 0)}
                    style={getRangeStyle(currentTime, duration)}
                    onChange={handleSeek}
                    aria-label="Audio progress"
                />
                <div className="post-audio-time">
                    <span>{formatTime(currentTime)}</span>
                    <span>{formatTime(duration)}</span>
                </div>
            </div>

            <div className={`post-audio-volume ${isVolumeExpanded ? "expanded" : ""}`}>
                <button
                    type="button"
                    className="post-audio-control"
                    onClick={() => setIsVolumeExpanded((prev) => !prev)}
                    aria-label="Volume"
                >
                    <VolumeIcon muted={volume === 0} />
                </button>
                <input
                    className="post-audio-volume-slider"
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={volume}
                    style={getRangeStyle(volume, 1)}
                    onChange={handleVolumeChange}
                    aria-label="Audio volume"
                />
            </div>
        </div>
    );
}

export default PostAudioPlayer;
