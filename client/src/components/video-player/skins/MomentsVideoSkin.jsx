import PauseIcon from "../../icons/PauseIcon";
import PlayIcon from "../../icons/PlayIcon";
import VolumeIcon from "../../icons/VolumeIcon";
import { useVideoPlayer } from "../core/VideoPlayerCore";
import Timeline from "../controls/Timeline";


function MomentsVideoSkin() {
    const { state, commands } = useVideoPlayer();

    return (
        <div className="video-player-skin moments">
            <Timeline compact />
            <div className="video-player-moments-controls">
                <button
                    type="button"
                    className="video-player-control primary"
                    onClick={commands.togglePlay}
                    aria-label={state.isPlaying ? "Pause Moment" : "Play Moment"}
                >
                    {state.isPlaying ? <PauseIcon /> : <PlayIcon />}
                </button>
                <button
                    type="button"
                    className="video-player-control"
                    onClick={commands.toggleMute}
                    aria-label={state.muted ? "Unmute Moment" : "Mute Moment"}
                >
                    <VolumeIcon muted={state.muted || state.volume === 0} />
                </button>
            </div>
        </div>
    );
}

export default MomentsVideoSkin;
