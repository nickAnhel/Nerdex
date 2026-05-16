import { fireEvent, render, screen, waitFor } from "@testing-library/react";

jest.mock("../..", () => ({
    StoreContext: require("react").createContext({
        store: {
            isAuthenticated: true,
            refreshPosts: jest.fn(),
        },
    }),
}));
jest.mock("react-router-dom", () => ({
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
    useNavigate: () => jest.fn(),
    useParams: () => ({ videoId: "video-1" }),
}), { virtual: true });
jest.mock("../../components/video-player/VideoPlayer", () => (props) => (
    <div data-testid="video-player">
        <span>{props.sources.map((source) => source.id).join(",")}</span>
        <button type="button" onClick={() => props.onPlay?.({ currentTime: 0, duration: 100 })}>play</button>
        <button type="button" onClick={() => props.onPause?.({ currentTime: 31, duration: 100 })}>pause</button>
    </div>
));
jest.mock("../../components/comment-section/CommentSection", () => () => <div />);
jest.mock("../../components/similar-content-block/SimilarContentBlock", () => () => <div />);
jest.mock("../../service/VideoService", () => ({
    __esModule: true,
    default: {
        getVideo: jest.fn(),
        deleteVideo: jest.fn(),
    },
}));
jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        startViewSession: jest.fn(),
        heartbeatViewSession: jest.fn(),
        finishViewSession: jest.fn(),
    },
}));

import VideoService from "../../service/VideoService";
import ContentService from "../../service/ContentService";
import VideoDetails from "./VideoDetails";


function readyVideo(overrides = {}) {
    return {
        video_id: "video-1",
        content_id: "video-1",
        title: "Ready video",
        description: "",
        user: { username: "author", avatar: null },
        cover: { preview_url: "https://cdn.example/cover.webp" },
        playback_sources: [{ id: "720p", src: "https://cdn.example/720.mp4" }],
        chapters: [],
        processing_status: "ready",
        status: "published",
        visibility: "public",
        comments_count: 0,
        likes_count: 0,
        dislikes_count: 0,
        views_count: 0,
        tags: [],
        created_at: "2026-05-04T00:00:00Z",
        published_at: "2026-05-04T00:00:00Z",
        ...overrides,
    };
}

beforeEach(() => {
    jest.clearAllMocks();
});

test("passes ready playback sources into existing VideoPlayer", async () => {
    VideoService.getVideo.mockResolvedValue({
        data: readyVideo(),
    });

    render(
        <VideoDetails />
    );

    await waitFor(() => expect(screen.getByTestId("video-player").textContent).toContain("720p"));
});

test("updates views count from view session heartbeat response", async () => {
    VideoService.getVideo.mockResolvedValue({ data: readyVideo() });
    ContentService.startViewSession.mockResolvedValue({
        data: {
            view_session_id: "session-1",
            content_id: "video-1",
            views_count: 0,
        },
    });
    ContentService.heartbeatViewSession.mockResolvedValue({
        data: {
            view_session_id: "session-1",
            content_id: "video-1",
            last_position_seconds: 31,
            max_position_seconds: 31,
            watched_seconds: 31,
            progress_percent: 31,
            is_counted: true,
            counted_at: "2026-05-04T00:00:31Z",
            views_count: 1,
        },
    });

    render(<VideoDetails />);

    await waitFor(() => expect(screen.getByText("0 views")).not.toBeNull());
    fireEvent.click(screen.getByText("play"));
    await waitFor(() => expect(ContentService.startViewSession).toHaveBeenCalled());
    fireEvent.click(screen.getByText("pause"));

    await waitFor(() => expect(screen.getByText("1 views")).not.toBeNull());
});
