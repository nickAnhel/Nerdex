import { useState } from "react";

import { useVideoPlayer } from "../core/VideoPlayerCore";


function QualityMenu({ compact = false }) {
    const { sources, state, commands } = useVideoPlayer();
    const [isOpen, setIsOpen] = useState(false);
    const activeSource = sources.find((source) => source.id === state.selectedQualityId);

    if (sources.length <= 1) {
        return (
            <span className={`video-player-static-value ${compact ? "compact" : ""}`}>
                {activeSource?.label || "Original"}
            </span>
        );
    }

    return (
        <div className="video-player-menu">
            <button
                type="button"
                className="video-player-control text"
                onClick={() => setIsOpen((prev) => !prev)}
                aria-label="Select video quality"
                aria-expanded={isOpen}
            >
                {activeSource?.label || "Quality"}
            </button>
            {isOpen && (
                <div className="video-player-menu-popover">
                    {sources.map((source) => (
                        <button
                            key={source.id}
                            type="button"
                            className={source.id === state.selectedQualityId ? "active" : ""}
                            onClick={() => {
                                commands.setQuality(source.id);
                                setIsOpen(false);
                            }}
                        >
                            {source.label}
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

export default QualityMenu;
