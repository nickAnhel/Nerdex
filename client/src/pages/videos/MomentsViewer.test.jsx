import { fireEvent, render, screen, waitFor } from "@testing-library/react";

let mockRouteSearch = "";

jest.mock("react-router-dom", () => ({
    useNavigate: () => jest.fn(),
    useSearchParams: () => [new URLSearchParams(mockRouteSearch)],
}), { virtual: true });

jest.mock("../..", () => ({
    StoreContext: require("react").createContext({
        store: {
            isAuthenticated: true,
        },
    }),
}));
jest.mock("../../components/video-player/VideoPlayer", () => (props) => (
    <div
        data-testid="video-player"
        data-skin={props.skin}
        data-autoplay={String(Boolean(props.autoPlay))}
    >
        <span>{props.sources.map((source) => source.id).join(",")}</span>
        <button type="button" onClick={() => props.onTimeUpdate?.({ currentTime: 2, duration: 30 })}>
            time
        </button>
        <button type="button" onClick={() => props.onEnded?.({ currentTime: 30, duration: 30 })}>
            ended
        </button>
    </div>
));
jest.mock("../../components/comment-section/CommentSection", () => (props) => (
    <div data-testid="comments-drawer">{props.contentId}</div>
));
jest.mock("../../components/loader/Loader", () => () => <div>Loading</div>);
jest.mock("../../service/MomentService", () => ({
    __esModule: true,
    default: {
        getFeed: jest.fn(),
        getMoment: jest.fn(),
        deleteMoment: jest.fn(),
    },
}));
jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        setReaction: jest.fn(),
        removeReaction: jest.fn(),
        startViewSession: jest.fn(),
        heartbeatViewSession: jest.fn(),
    },
}));

import ContentService from "../../service/ContentService";
import MomentService from "../../service/MomentService";
import MomentsViewer from "./MomentsViewer";


function moment(overrides = {}) {
    return {
        moment_id: "moment-1",
        content_id: "moment-1",
        content_type: "moment",
        caption: "A short Moment",
        user: { username: "author", avatar: null },
        cover: { preview_url: "https://cdn.example/cover.webp" },
        playback_sources: [{ id: "720p", src: "https://cdn.example/720.mp4", mimeType: "video/mp4" }],
        processing_status: "ready",
        status: "published",
        visibility: "public",
        comments_count: 2,
        likes_count: 3,
        dislikes_count: 1,
        views_count: 0,
        duration_seconds: 30,
        is_owner: false,
        tags: [],
        created_at: "2026-05-06T00:00:00Z",
        published_at: "2026-05-06T00:00:00Z",
        ...overrides,
    };
}

beforeEach(() => {
    jest.clearAllMocks();
    MomentService.getFeed.mockResolvedValue({
        data: [
            moment(),
            moment({ moment_id: "moment-2", content_id: "moment-2", caption: "Second Moment", user: { username: "second" } }),
        ],
    });
    MomentService.getMoment.mockResolvedValue({
        data: moment({ moment_id: "moment-3", content_id: "moment-3", caption: "Deep linked Moment", user: { username: "target" } }),
    });
    ContentService.startViewSession.mockResolvedValue({
        data: { view_session_id: "session-1" },
    });
    ContentService.heartbeatViewSession.mockResolvedValue({
        data: { views_count: 1 },
    });
});

function renderViewer(route = "/moments") {
    mockRouteSearch = route.split("?")[1] || "";
    return render(<MomentsViewer />);
}

test("renders MomentSlide with VideoPlayer moments skin and no raw video element", async () => {
    renderViewer();

    await waitFor(() => expect(screen.getAllByTestId("moment-slide").length).toBeGreaterThan(0));

    expect(screen.getByText("A short Moment")).not.toBeNull();
    expect(screen.getAllByTestId("video-player")[0].dataset.skin).toBe("moments");
    expect(document.querySelector("video")).toBeNull();
});

test("keeps only one active slide playing when moving through feed", async () => {
    renderViewer();

    await waitFor(() => expect(screen.getByText("A short Moment")).not.toBeNull());
    expect(screen.getAllByTestId("video-player")).toHaveLength(2);
    expect(screen.getAllByTestId("video-player").filter((node) => node.dataset.autoplay === "true")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: /next moment/i }));

    await waitFor(() => expect(screen.getByText("Second Moment")).not.toBeNull());
    expect(screen.getAllByTestId("video-player")).toHaveLength(2);
    expect(screen.getAllByTestId("video-player").filter((node) => node.dataset.autoplay === "true")).toHaveLength(1);
});

test("uses generic content reactions and opens comments drawer", async () => {
    ContentService.setReaction.mockResolvedValue({
        data: {
            content_id: "moment-1",
            likes_count: 4,
            dislikes_count: 1,
            my_reaction: "like",
        },
    });

    renderViewer();

    await waitFor(() => expect(screen.getByText("A short Moment")).not.toBeNull());
    fireEvent.click(screen.getAllByRole("button", { name: /^like moment$/i })[0]);

    await waitFor(() => expect(ContentService.setReaction).toHaveBeenCalledWith("moment-1", "like"));

    fireEvent.click(screen.getAllByRole("button", { name: /open moment comments/i })[0]);
    expect(screen.getByTestId("comments-drawer").textContent).toBe("moment-1");
});

test("active Moment sends view heartbeat from VideoPlayer time updates", async () => {
    renderViewer();

    await waitFor(() => expect(screen.getByText("A short Moment")).not.toBeNull());
    fireEvent.click(screen.getAllByText("time")[0]);

    await waitFor(() => expect(ContentService.startViewSession).toHaveBeenCalledWith("moment-1", expect.objectContaining({
        source: "moments_feed",
    })));
    await waitFor(() => expect(ContentService.heartbeatViewSession).toHaveBeenCalledWith(
        "moment-1",
        "session-1",
        expect.objectContaining({
            position_seconds: 2,
            watched_seconds_delta: 2,
        }),
    ));
});

test("opens a deep-linked Moment before the rest of the feed", async () => {
    renderViewer("/moments?moment=moment-3");

    await waitFor(() => expect(screen.getByText("Deep linked Moment")).not.toBeNull());
    expect(MomentService.getMoment).toHaveBeenCalledWith("moment-3");
});

test("supports keyboard and touch navigation", async () => {
    renderViewer();

    await waitFor(() => expect(screen.getByText("A short Moment")).not.toBeNull());

    fireEvent.keyDown(window, { key: "ArrowDown" });
    await waitFor(() => expect(screen.getByText("Second Moment")).not.toBeNull());

    fireEvent.touchStart(document.querySelector(".moments-viewer"), {
        touches: [{ clientY: 120 }],
    });
    fireEvent.touchEnd(document.querySelector(".moments-viewer"), {
        changedTouches: [{ clientY: 220 }],
    });
    await waitFor(() => expect(screen.getByText("A short Moment")).not.toBeNull());
});
