import { getRangeProgress } from "../utils/time";
import { useVideoPlayer } from "../core/VideoPlayerCore";


function Timeline({ compact = false }) {
    const { state, commands, chapters } = useVideoPlayer();
    const duration = state.duration || 0;
    const currentProgress = getRangeProgress(state.currentTime, duration);
    const bufferedProgress = getRangeProgress(state.bufferedEnd, duration);

    const handleSeek = (event) => {
        commands.seekTo(Number(event.target.value));
    };

    return (
        <div className={`video-player-timeline ${compact ? "compact" : ""}`}>
            <div
                className="video-player-timeline-track"
                style={{
                    "--video-progress": `${currentProgress}%`,
                    "--video-buffered": `${bufferedProgress}%`,
                }}
            >
                {chapters.map((chapter) => {
                    const markerPosition = getRangeProgress(chapter.startsAtSeconds, duration);
                    return (
                        <button
                            key={chapter.id}
                            type="button"
                            className="video-player-chapter-marker"
                            style={{ left: `${markerPosition}%` }}
                            onClick={() => commands.jumpToChapter(chapter)}
                            title={chapter.title}
                            aria-label={`Jump to chapter ${chapter.title}`}
                        />
                    );
                })}
                <input
                    type="range"
                    min="0"
                    max={duration || 0}
                    step="0.1"
                    value={Math.min(state.currentTime, duration)}
                    onChange={handleSeek}
                    aria-label="Video progress"
                />
            </div>
        </div>
    );
}

export default Timeline;
