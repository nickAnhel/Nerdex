import { render, screen } from "@testing-library/react";

jest.mock("../..", () => ({
    StoreContext: require("react").createContext({
        store: {
            isAuthenticated: false,
            refreshPosts: jest.fn(),
        },
    }),
}));
jest.mock("react-router-dom", () => ({
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
    useNavigate: () => jest.fn(),
}), { virtual: true });
jest.mock("../../service/VideoService", () => ({
    __esModule: true,
    default: {
        likeVideo: jest.fn(),
        unlikeVideo: jest.fn(),
        dislikeVideo: jest.fn(),
        undislikeVideo: jest.fn(),
        deleteVideo: jest.fn(),
    },
}));

import VideoCard from "./VideoCard";


const video = {
    video_id: "video-1",
    content_id: "video-1",
    content_type: "video",
    title: "A useful video",
    excerpt: "A short description",
    user: { username: "author", avatar: null },
    cover: { preview_url: "https://cdn.example/cover.webp" },
    duration_seconds: 83,
    orientation: "landscape",
    processing_status: "ready",
    status: "published",
    visibility: "public",
    comments_count: 2,
    likes_count: 3,
    dislikes_count: 1,
    tags: [],
    canonical_path: "/videos/video-1",
    created_at: "2026-05-04T00:00:00Z",
    published_at: "2026-05-04T00:00:00Z",
};


test("renders preview and duration without mounting playback", () => {
    render(
        <VideoCard video={video} />
    );

    expect(screen.getByText("A useful video")).not.toBeNull();
    expect(screen.getByText("1:23")).not.toBeNull();
    expect(screen.getByAltText("A useful video").getAttribute("src")).toBe(video.cover.preview_url);
    expect(document.querySelector("video")).toBeNull();
});
