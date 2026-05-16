import { render, screen, waitFor } from "@testing-library/react";

let mockStore = {
    isAuthenticated: true,
};
let mockSearch = "p=post-1";

jest.mock("../..", () => ({
    StoreContext: require("react").createContext({
        get store() {
            return mockStore;
        },
    }),
}));
jest.mock("react-router-dom", () => ({
    useSearchParams: () => [
        new URLSearchParams(mockSearch),
        jest.fn(),
    ],
}), { virtual: true });
jest.mock("../../components/loader/Loader", () => () => <div>Loading</div>);
jest.mock("../../components/comment-section/CommentSection", () => () => <div />);
jest.mock("../../components/modal/Modal", () => ({ children }) => <div>{children}</div>);
jest.mock("../../components/post-list-item/PostListItem", () => ({ post }) => <div>{post.content}</div>);
jest.mock("../../components/similar-content-block/SimilarContentBlock", () => () => <div />);
jest.mock("../../service/PostService", () => ({
    __esModule: true,
    default: {
        getPost: jest.fn(),
    },
}));
jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        startViewSession: jest.fn(),
    },
}));

import ContentService from "../../service/ContentService";
import PostService from "../../service/PostService";
import PostDetails from "./PostDetails";


function post(overrides = {}) {
    return {
        post_id: "post-1",
        content: "Tracked post",
        status: "published",
        ...overrides,
    };
}

beforeEach(() => {
    jest.clearAllMocks();
    mockStore = { isAuthenticated: true };
    mockSearch = "p=post-1";
    PostService.getPost.mockResolvedValue({ data: post() });
    ContentService.startViewSession.mockResolvedValue({ data: { view_session_id: "session-1" } });
});

test("authenticated post detail starts a view session", async () => {
    render(<PostDetails />);

    await waitFor(() => expect(screen.getByText("Tracked post")).not.toBeNull());
    await waitFor(() => expect(ContentService.startViewSession).toHaveBeenCalledWith(
        "post-1",
        expect.objectContaining({
            source: "post_detail",
            initial_progress_percent: 100,
        }),
    ));
});

test("unauthenticated post detail does not start a view session", async () => {
    mockStore = { isAuthenticated: false };

    render(<PostDetails />);

    await waitFor(() => expect(screen.getByText("Tracked post")).not.toBeNull());
    expect(ContentService.startViewSession).not.toHaveBeenCalled();
});

test("post tracking failure does not break rendering", async () => {
    const consoleSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    ContentService.startViewSession.mockRejectedValue(new Error("tracking failed"));

    render(<PostDetails />);

    await waitFor(() => expect(screen.getByText("Tracked post")).not.toBeNull());
    consoleSpy.mockRestore();
});
