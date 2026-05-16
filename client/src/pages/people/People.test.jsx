import { render, screen, waitFor, fireEvent } from "@testing-library/react";

import { StoreContext } from "../..";
import People from "./People";


jest.mock("../..", () => {
    const React = require("react");
    return {
        StoreContext: React.createContext({ store: {} }),
    };
});


jest.mock("react-router-dom", () => {
    const React = require("react");
    return {
        useNavigate: () => jest.fn(),
        Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
    };
}, { virtual: true });

jest.mock("../../components/global-search-input/GlobalSearchInput", () => ({
    value,
    onChange,
    onSubmit,
}) => (
    <div>
        <input aria-label="people-search" value={value} onChange={(event) => onChange(event.target.value)} />
        <button type="button" onClick={() => onSubmit(value)}>Search</button>
    </div>
));

jest.mock("../../components/loader/Loader", () => () => <div>Loading</div>);

jest.mock("../../service/UserService", () => ({
    __esModule: true,
    default: {
        getSubscriptions: jest.fn(),
        subscribeToUser: jest.fn(),
        unsubscribeFromUser: jest.fn(),
    },
}));

jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        getRecommendedAuthors: jest.fn(),
    },
}));

import UserService from "../../service/UserService";
import ContentService from "../../service/ContentService";


function renderPeople(storeOverrides = {}) {
    const store = {
        isAuthenticated: true,
        user: {
            user_id: "viewer-id",
        },
        ...storeOverrides,
    };

    return render(
        <StoreContext.Provider value={{ store }}>
            <People />
        </StoreContext.Provider>
    );
}


beforeEach(() => {
    jest.clearAllMocks();
});


test("renders two columns and moves author from recommendations to subscriptions after follow", async () => {
    UserService.getSubscriptions.mockResolvedValue({
        data: [
            {
                user_id: "sub-1",
                username: "subscribed-author",
                display_name: "Subscribed Author",
                bio: "Existing subscription",
                subscribers_count: 3,
                is_subscribed: true,
            },
        ],
    });
    ContentService.getRecommendedAuthors.mockResolvedValue({
        data: [
            {
                user_id: "rec-1",
                score: 10.5,
                reason: "topic_author_affinity",
                author: {
                    user_id: "rec-1",
                    username: "recommended-author",
                    display_name: "Recommended Author",
                    bio: "Recommended profile",
                    subscribers_count: 9,
                    is_subscribed: false,
                },
            },
        ],
    });
    UserService.subscribeToUser.mockResolvedValue({});

    renderPeople();

    expect(screen.getByRole("heading", { name: "Subscriptions" })).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Recommended authors" })).not.toBeNull();

    await waitFor(() => expect(screen.getByText("Subscribed Author")).not.toBeNull());
    await waitFor(() => expect(screen.getByText("Recommended Author")).not.toBeNull());

    fireEvent.click(screen.getByRole("button", { name: "Follow" }));

    await waitFor(() => expect(UserService.subscribeToUser).toHaveBeenCalledWith("rec-1"));
    await waitFor(() => expect(screen.queryByText("No recommended authors yet.")).not.toBeNull());
    expect(screen.getByText("Recommended Author")).not.toBeNull();
});


test("unfollow removes author from subscriptions list without full page reload", async () => {
    UserService.getSubscriptions.mockResolvedValue({
        data: [
            {
                user_id: "sub-2",
                username: "to-unfollow",
                display_name: "To Unfollow",
                bio: "Will be removed",
                subscribers_count: 7,
                is_subscribed: true,
            },
        ],
    });
    ContentService.getRecommendedAuthors.mockResolvedValue({ data: [] });
    UserService.unsubscribeFromUser.mockResolvedValue({});

    renderPeople();

    await waitFor(() => expect(screen.getByText("To Unfollow")).not.toBeNull());

    fireEvent.click(screen.getByRole("button", { name: "Unfollow" }));

    await waitFor(() => expect(UserService.unsubscribeFromUser).toHaveBeenCalledWith("sub-2"));
    await waitFor(() => expect(screen.getByText("You are not subscribed to any authors yet.")).not.toBeNull());
});


test("handles independent error and empty states per column", async () => {
    UserService.getSubscriptions.mockRejectedValue({
        response: { data: { detail: "Subscriptions failed" } },
    });
    ContentService.getRecommendedAuthors.mockResolvedValue({ data: [] });

    renderPeople();

    await waitFor(() => expect(screen.getByText("Subscriptions failed")).not.toBeNull());
    await waitFor(() => expect(screen.getByText("No recommended authors yet.")).not.toBeNull());
});
