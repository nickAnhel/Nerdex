import { fireEvent, render, screen, waitFor } from "@testing-library/react";

let mockStore = {
    isAuthenticated: true,
};

jest.mock("../..", () => ({
    StoreContext: require("react").createContext({
        get store() {
            return mockStore;
        },
    }),
}));
jest.mock("react-router-dom", () => ({
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}), { virtual: true });
jest.mock("../../components/feed-content-card/FeedContentCard", () => ({ item }) => (
    <div>Content card: {item.content_id}</div>
));
jest.mock("../../components/loader/Loader", () => () => <div>Loading</div>);
jest.mock("../../components/unauthorized/Unauthorized", () => () => <div>Unauthorized</div>);
jest.mock("../../utils/avatar", () => ({
    getAvatarUrl: () => "/avatar.png",
}));
jest.mock("../../service/ActivityService", () => ({
    __esModule: true,
    default: {
        getActivity: jest.fn(),
    },
}));

import ActivityService from "../../service/ActivityService";
import Activity from "./Activity";


function response(items = []) {
    return {
        data: {
            items,
            offset: 0,
            limit: 20,
            has_more: false,
        },
    };
}


function contentEvent() {
    return {
        activity_event_id: "event-1",
        action_type: "content_like",
        created_at: "2026-05-13T10:00:00Z",
        content_type: "article",
        content: {
            content_id: "article-1",
            content_type: "article",
        },
        target_user: null,
        comment: null,
        metadata: {},
    };
}


function followEvent() {
    return {
        activity_event_id: "event-2",
        action_type: "user_follow",
        created_at: "2026-05-13T11:00:00Z",
        content_type: null,
        content: null,
        target_user: {
            user_id: "user-1",
            username: "author",
            subscribers_count: 3,
            avatar: null,
        },
        comment: null,
        metadata: {},
    };
}


beforeEach(() => {
    jest.clearAllMocks();
    mockStore = { isAuthenticated: true };
    ActivityService.getActivity.mockResolvedValue(response());
});


test("loads activity events", async () => {
    ActivityService.getActivity.mockResolvedValue(response([contentEvent(), followEvent()]));

    render(<Activity />);

    await waitFor(() => expect(screen.getByText("You liked an article")).not.toBeNull());
    expect(screen.getByText("Content card: article-1")).not.toBeNull();
    expect(screen.getByText("You followed an author")).not.toBeNull();
    expect(screen.getByText("author")).not.toBeNull();
});


test("filters call API with correct params", async () => {
    render(<Activity />);

    await waitFor(() => expect(ActivityService.getActivity).toHaveBeenCalled());
    fireEvent.click(screen.getByText("Likes"));

    await waitFor(() => expect(ActivityService.getActivity).toHaveBeenLastCalledWith(
        expect.objectContaining({
            action_type: ["content_like"],
            period: "week",
            offset: 0,
            limit: 20,
        }),
    ));

    fireEvent.click(screen.getByText("Authors"));

    await waitFor(() => expect(ActivityService.getActivity).toHaveBeenLastCalledWith(
        expect.objectContaining({
            action_type: ["user_follow", "user_unfollow"],
            period: "week",
            offset: 0,
            limit: 20,
        }),
    ));
});


test("empty state works", async () => {
    render(<Activity />);

    await waitFor(() => expect(screen.getByText("No activity matches these filters")).not.toBeNull());
});


test("error state works", async () => {
    ActivityService.getActivity.mockRejectedValue(new Error("failed"));

    render(<Activity />);

    await waitFor(() => expect(screen.getByText("Activity could not be loaded")).not.toBeNull());
});


test("unauthenticated users see unauthorized state", () => {
    mockStore = { isAuthenticated: false };

    render(<Activity />);

    expect(screen.getByText("Unauthorized")).not.toBeNull();
});
