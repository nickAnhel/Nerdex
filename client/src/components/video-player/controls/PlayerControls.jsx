import FullscreenExitIcon from "../../icons/FullscreenExitIcon";
import FullscreenIcon from "../../icons/FullscreenIcon";
import PauseIcon from "../../icons/PauseIcon";
import PlayIcon from "../../icons/PlayIcon";
import VolumeIcon from "../../icons/VolumeIcon";
import { useVideoPlayer } from "../core/VideoPlayerCore";
import { formatVideoTime, getRangeProgress } from "../utils/time";
import QualityMenu from "./QualityMenu";
import SpeedMenu from "./SpeedMenu";
import Timeline from "./Timeline";


function PlayerControls({ density = "default", showChapters = false }) {
    const { state, commands, chapters } = useVideoPlayer();
    const compact = density !== "default";
    const volumeProgress = getRangeProgress(state.volume, 1);

    return (
        <div className={`video-player-controls ${density}`}>
            <Timeline compact={compact} />

            <div className="video-player-control-row">
                <div className="video-player-control-group main">
                    <button
                        type="button"
                        className="video-player-control primary"
                        onClick={commands.togglePlay}
                        aria-label={state.isPlaying ? "Pause video" : "Play video"}
                    >
                        {state.isPlaying ? <PauseIcon /> : <PlayIcon />}
                    </button>

                    <div className="video-player-time">
                        <span>{formatVideoTime(state.currentTime)}</span>
                        <span>/</span>
                        <span>{formatVideoTime(state.duration)}</span>
                    </div>

                    <button
                        type="button"
                        className="video-player-control"
                        onClick={commands.toggleMute}
                        aria-label={state.muted ? "Unmute video" : "Mute video"}
                    >
                        <VolumeIcon muted={state.muted || state.volume === 0} />
                    </button>

                    <input
                        className="video-player-volume"
                        type="range"
                        min="0"
                        max="1"
                        step="0.01"
                        value={state.muted ? 0 : state.volume}
                        style={{ "--video-volume": `${volumeProgress}%` }}
                        onChange={(event) => commands.setVolume(Number(event.target.value))}
                        aria-label="Video volume"
                    />
                </div>

                <div className="video-player-control-group settings">
                    {!compact && <SpeedMenu />}
                    <QualityMenu compact={compact} />

                    <button
                        type="button"
                        className="video-player-control"
                        onClick={commands.toggleFullscreen}
                        aria-label={state.isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
                        title={state.isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
                    >
                        {state.isFullscreen ? <FullscreenExitIcon /> : <FullscreenIcon />}
                    </button>
                </div>
            </div>

            {showChapters && chapters.length > 0 && (
                <div className="video-player-chapters">
                    {chapters.map((chapter) => (
                        <button
                            key={chapter.id}
                            type="button"
                            onClick={() => commands.jumpToChapter(chapter)}
                        >
                            <span>{formatVideoTime(chapter.startsAtSeconds)}</span>
                            <span>{chapter.title}</span>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

export default PlayerControls;
