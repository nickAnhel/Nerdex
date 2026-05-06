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
}), { virtual: true });
jest.mock("../../service/VideoService", () => ({
    __esModule: true,
    default: {
        deleteVideo: jest.fn(),
    },
}));
jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        setReaction: jest.fn(),
        removeReaction: jest.fn(),
    },
}));

import VideoCard from "./VideoCard";
import ContentService from "../../service/ContentService";


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

test("uses generic content reactions for video likes", async () => {
    ContentService.setReaction.mockResolvedValue({
        data: {
            content_id: "video-1",
            likes_count: 4,
            dislikes_count: 1,
            my_reaction: "like",
        },
    });

    render(<VideoCard video={video} />);

    fireEvent.click(screen.getAllByRole("button")[2]);

    await waitFor(() => expect(ContentService.setReaction).toHaveBeenCalledWith("video-1", "like"));
});
