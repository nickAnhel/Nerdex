import { useState } from "react";

import { useVideoPlayer } from "../core/VideoPlayerCore";
import { PLAYBACK_SPEEDS } from "../core/videoPlayerTypes";


function SpeedMenu() {
    const { state, commands } = useVideoPlayer();
    const [isOpen, setIsOpen] = useState(false);

    return (
        <div className="video-player-menu">
            <button
                type="button"
                className="video-player-control text"
                onClick={() => setIsOpen((prev) => !prev)}
                aria-label="Select playback speed"
                aria-expanded={isOpen}
            >
                {state.playbackRate}x
            </button>
            {isOpen && (
                <div className="video-player-menu-popover">
                    {PLAYBACK_SPEEDS.map((speed) => (
                        <button
                            key={speed}
                            type="button"
                            className={speed === state.playbackRate ? "active" : ""}
                            onClick={() => {
                                commands.setPlaybackRate(speed);
                                setIsOpen(false);
                            }}
                        >
                            {speed}x
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

export default SpeedMenu;
