import PlayerControls from "../controls/PlayerControls";
import { useVideoPlayer } from "../core/VideoPlayerCore";


function PageVideoSkin() {
    const { title } = useVideoPlayer();

    return (
        <div className="video-player-skin page">
            {title && <h2 className="video-player-title">{title}</h2>}
            <PlayerControls showChapters />
        </div>
    );
}

export default PageVideoSkin;
