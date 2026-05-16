import { fireEvent, render, screen, waitFor } from "@testing-library/react";

let mockLocationSearch = "";

jest.mock("react-router-dom", () => {
    const React = require("react");

    return {
        useSearchParams: () => {
            const [params, setParams] = React.useState(() => new URLSearchParams(mockLocationSearch));

            const setSearchParams = (nextParams) => {
                setParams(new URLSearchParams(nextParams.toString()));
            };

            return [params, setSearchParams];
        },
    };
}, { virtual: true });

jest.mock("../../components/global-search-input/GlobalSearchInput", () => ({
    value,
    onChange,
    onSubmit,
}) => (
    <div>
        <input
            aria-label="search-input"
            value={value}
            onChange={(event) => onChange(event.target.value)}
        />
        <button type="button" onClick={() => onSubmit(value)}>
            Submit Search
        </button>
    </div>
));

jest.mock("../../components/feed-content-card/FeedContentCard", () => ({ item }) => (
    <div>Content card: {item.content_id}</div>
));

jest.mock("../../components/user-list-item/UserListItem", () => ({ user }) => (
    <div>User item: {user.username}</div>
));

jest.mock("../../components/loader/Loader", () => () => <div>Loading</div>);

jest.mock("@siberiacancode/reactuse", () => {
    const React = require("react");

    return {
        useQuery: (fetcher, { keys = [] } = {}) => {
            const [state, setState] = React.useState({
                isLoading: true,
                isError: false,
                error: null,
                data: undefined,
            });

            React.useEffect(() => {
                let active = true;
                setState((prev) => ({ ...prev, isLoading: true, isError: false, error: null }));

                Promise.resolve()
                    .then(() => fetcher())
                    .then((data) => {
                        if (!active) {
                            return;
                        }
                        setState({
                            isLoading: false,
                            isError: false,
                            error: null,
                            data,
                        });
                    })
                    .catch((error) => {
                        if (!active) {
                            return;
                        }
                        setState({
                            isLoading: false,
                            isError: true,
                            error,
                            data: undefined,
                        });
                    });

                return () => {
                    active = false;
                };
            }, keys);

            return state;
        },
    };
});

jest.mock("../../service/SearchService", () => ({
    __esModule: true,
    default: {
        search: jest.fn(),
        popular: jest.fn(),
        popularAuthors: jest.fn(),
    },
}));

import SearchService from "../../service/SearchService";
import SearchResults from "./SearchResults";


function renderSearchPage(initialSearch) {
    mockLocationSearch = initialSearch;
    return render(<SearchResults />);
}


function contentResponse(contentId = "content-1") {
    return {
        data: {
            items: [
                {
                    result_type: "content",
                    content: {
                        content_id: contentId,
                        content_type: "post",
                    },
                    author: null,
                    score: 17,
                },
            ],
            offset: 0,
            limit: 20,
            has_more: false,
        },
    };
}


beforeEach(() => {
    jest.clearAllMocks();
    SearchService.search.mockResolvedValue(contentResponse("search-content"));
    SearchService.popular.mockResolvedValue(contentResponse("popular-content"));
    SearchService.popularAuthors.mockResolvedValue({
        data: {
            items: [
                {
                    result_type: "author",
                    content: null,
                    author: {
                        user_id: "popular-author-1",
                        username: "popular-creator",
                    },
                    score: 10,
                },
            ],
            offset: 0,
            limit: 6,
            has_more: false,
        },
    });
});


test("/search without q loads popular mode and hides authors filter", async () => {
    renderSearchPage("type=all&period=week");

    await waitFor(() => expect(SearchService.popular).toHaveBeenCalledWith(
        expect.objectContaining({
            type: "all",
            period: "week",
            offset: 0,
            limit: 20,
        })
    ));
    await waitFor(() => expect(SearchService.popularAuthors).toHaveBeenCalledWith(
        expect.objectContaining({
            period: "week",
            offset: 0,
            limit: 6,
        })
    ));

    expect(screen.getByRole("heading", { name: "Popular" })).not.toBeNull();
    expect(screen.queryByRole("button", { name: "Authors" })).toBeNull();
    expect(screen.queryByText("Sort")).toBeNull();
    expect(screen.getByText("Period")).not.toBeNull();
    expect(screen.getByText("Content card: popular-content")).not.toBeNull();
    expect(screen.getByText("Popular authors")).not.toBeNull();
    expect(screen.getByText("User item: popular-creator")).not.toBeNull();
});


test("/search?q=something loads search results mode with authors and sort", async () => {
    SearchService.search.mockResolvedValue({
        data: {
            items: [
                {
                    result_type: "author",
                    content: null,
                    author: {
                        user_id: "author-1",
                        username: "creator",
                    },
                    score: 0.9,
                },
            ],
            offset: 0,
            limit: 20,
            has_more: false,
        },
    });

    renderSearchPage("q=something&type=all&sort=relevance&period=week");

    await waitFor(() => expect(SearchService.search).toHaveBeenCalledWith(
        expect.objectContaining({
            q: "something",
            type: "all",
            sort: "relevance",
            offset: 0,
            limit: 20,
        })
    ));

    expect(screen.getByRole("heading", { name: "Search" })).not.toBeNull();
    expect(screen.getByRole("button", { name: "Authors" })).not.toBeNull();
    expect(screen.getByText("Sort")).not.toBeNull();
    expect(screen.queryByText("Period")).toBeNull();
    expect(screen.getByText("User item: creator")).not.toBeNull();
    expect(SearchService.popular).not.toHaveBeenCalled();
    expect(SearchService.popularAuthors).not.toHaveBeenCalled();
});


test("popular mode normalizes unsupported author type to all", async () => {
    renderSearchPage("type=author&period=month");

    await waitFor(() => expect(SearchService.popular).toHaveBeenCalledWith(
        expect.objectContaining({
            type: "all",
            period: "month",
        })
    ));
    await waitFor(() => expect(SearchService.popularAuthors).toHaveBeenCalledWith(
        expect.objectContaining({
            period: "month",
            offset: 0,
            limit: 6,
        })
    ));

    expect(screen.queryByRole("button", { name: "Authors" })).toBeNull();
});


test("changing period resets pagination and refetches popular", async () => {
    renderSearchPage("type=post&period=week&offset=40&limit=20");

    await waitFor(() => expect(SearchService.popular).toHaveBeenCalledWith(
        expect.objectContaining({
            type: "post",
            period: "week",
            offset: 40,
            limit: 20,
        })
    ));

    fireEvent.change(screen.getByLabelText("Period"), {
        target: { value: "month" },
    });

    await waitFor(() => expect(SearchService.popular).toHaveBeenLastCalledWith(
        expect.objectContaining({
            type: "post",
            period: "month",
            offset: 0,
            limit: 20,
        })
    ));
    await waitFor(() => expect(SearchService.popularAuthors).toHaveBeenLastCalledWith(
        expect.objectContaining({
            period: "month",
            offset: 0,
            limit: 6,
        })
    ));
});
