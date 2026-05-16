import { fireEvent, render, screen, waitFor } from "@testing-library/react";

let mockLocationSearch = "";
const mockContentListSpy = jest.fn();

jest.mock("react-router-dom", () => {
    const React = require("react");

    return {
        useSearchParams: () => {
            const [params, setParams] = React.useState(() => new URLSearchParams(mockLocationSearch));

            const setSearchParams = (nextParams) => {
                if (nextParams instanceof URLSearchParams) {
                    setParams(new URLSearchParams(nextParams));
                    return;
                }
                if (typeof nextParams === "string") {
                    setParams(new URLSearchParams(nextParams));
                    return;
                }
                setParams(new URLSearchParams(nextParams));
            };

            return [params, setSearchParams];
        },
    };
}, { virtual: true });

jest.mock("../..", () => {
    const React = require("react");
    return {
        StoreContext: React.createContext({ store: {} }),
    };
}, { virtual: true });

jest.mock("../../components/content-list/ContentList", () => (props) => {
    mockContentListSpy(props);
    return <div data-testid="content-list" />;
});

jest.mock("../../components/feed-content-card/FeedContentCard", () => () => <div />);

jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        getRecommendationsFeed: jest.fn(),
        getSubscriptionsFeed: jest.fn(),
    },
}));

import ContentService from "../../service/ContentService";
import GlobalFeed from "./GlobalFeed";
import { StoreContext } from "../..";


function renderFeed({ initialSearch = "", isAuthenticated = false } = {}) {
    mockLocationSearch = initialSearch;
    const store = {
        isAuthenticated,
        isRefreshPosts: false,
    };
    return render(
        <StoreContext.Provider value={{ store }}>
            <GlobalFeed />
        </StoreContext.Provider>
    );
}


beforeEach(() => {
    jest.clearAllMocks();
});


test("feed shows recommendations tab by default and does not expose popular tab", () => {
    renderFeed();

    expect(screen.getByRole("button", { name: "Recommendations" })).not.toBeNull();
    expect(screen.queryByRole("button", { name: "Subscriptions" })).toBeNull();
    expect(screen.queryByText("Popular")).toBeNull();

    const props = mockContentListSpy.mock.calls.at(-1)[0];
    expect(props.fetchItems).toBe(ContentService.getRecommendationsFeed);
    expect(props.filters).toEqual({
        content_type: "all",
        sort: "relevance",
    });
});


test("subscriptions mode maps sort and content type to subscriptions endpoint filters", async () => {
    renderFeed({ isAuthenticated: true });

    expect(screen.getByRole("button", { name: "Subscriptions" })).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Subscriptions" }));
    fireEvent.click(screen.getByRole("button", { name: "Videos" }));
    fireEvent.change(screen.getByLabelText("Sort"), { target: { value: "oldest" } });

    await waitFor(() => {
        expect(screen.queryByRole("option", { name: "Relevance" })).toBeNull();
        const props = mockContentListSpy.mock.calls.at(-1)[0];
        expect(props.fetchItems).toBe(ContentService.getSubscriptionsFeed);
        expect(props.filters).toEqual({
            content_type: "video",
            order: "published_at",
            desc: false,
        });
    });
});
