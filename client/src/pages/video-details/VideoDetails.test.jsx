import { render, screen, waitFor } from "@testing-library/react";

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
    <div data-testid="video-player">{props.sources.map((source) => source.id).join(",")}</div>
));
jest.mock("../../components/comment-section/CommentSection", () => () => <div />);
jest.mock("../../service/VideoService", () => ({
    __esModule: true,
    default: {
        getVideo: jest.fn(),
        deleteVideo: jest.fn(),
    },
}));

import VideoService from "../../service/VideoService";
import VideoDetails from "./VideoDetails";


test("passes ready playback sources into existing VideoPlayer", async () => {
    VideoService.getVideo.mockResolvedValue({
        data: {
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
            tags: [],
            created_at: "2026-05-04T00:00:00Z",
            published_at: "2026-05-04T00:00:00Z",
        },
    });

    render(
        <VideoDetails />
    );

    await waitFor(() => expect(screen.getByTestId("video-player").textContent).toBe("720p"));
});
