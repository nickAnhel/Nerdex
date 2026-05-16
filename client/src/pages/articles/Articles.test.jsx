import { fireEvent, render, screen, waitFor } from "@testing-library/react";

let mockLocationSearch = "";
const mockContentListSpy = jest.fn();

jest.mock("react-router-dom", () => {
    const React = require("react");

    return {
        useNavigate: () => jest.fn(),
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

jest.mock("../../components/global-search-input/GlobalSearchInput", () => () => <div />);
jest.mock("../../components/article-card/ArticleCard", () => () => <div />);
jest.mock("../../components/content-list/ContentList", () => (props) => {
    mockContentListSpy(props);
    return <div data-testid="articles-content-list" />;
});

jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        getRecommendationsFeed: jest.fn(),
        getSubscriptionsFeed: jest.fn(),
    },
}));

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";
import Articles from "./Articles";


function renderArticles({ initialSearch = "", isAuthenticated = false } = {}) {
    mockLocationSearch = initialSearch;
    const store = {
        isAuthenticated,
        isRefreshPosts: false,
    };
    return render(
        <StoreContext.Provider value={{ store }}>
            <Articles />
        </StoreContext.Provider>
    );
}


beforeEach(() => {
    jest.clearAllMocks();
});


test("articles default to recommendations section", () => {
    renderArticles();

    const props = mockContentListSpy.mock.calls.at(-1)[0];
    expect(props.fetchItems).toBe(ContentService.getRecommendationsFeed);
    expect(props.filters).toEqual({
        content_type: "article",
        sort: "relevance",
    });
});


test("articles subscriptions section uses subscriptions feed for authenticated users", async () => {
    renderArticles({ isAuthenticated: true });

    fireEvent.click(screen.getByRole("button", { name: "Subscriptions" }));

    await waitFor(() => {
        const props = mockContentListSpy.mock.calls.at(-1)[0];
        expect(props.fetchItems).toBe(ContentService.getSubscriptionsFeed);
        expect(props.filters).toEqual({
            content_type: "article",
            order: "published_at",
            desc: true,
        });
    });
});
