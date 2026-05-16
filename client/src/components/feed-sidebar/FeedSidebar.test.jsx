import { fireEvent, render, screen } from "@testing-library/react";

const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
    NavLink: ({ children, to, className }) => (
        <a href={to} className={typeof className === "function" ? className({}) : className}>
            {children}
        </a>
    ),
    useNavigate: () => mockNavigate,
    useLocation: () => ({ search: "" }),
}), { virtual: true });

jest.mock("../..", () => {
    const React = require("react");
    return {
        StoreContext: React.createContext({ store: {} }),
    };
}, { virtual: true });

jest.mock("../global-search-input/GlobalSearchInput", () => ({
    value,
    onChange,
    onSubmit,
}) => (
    <div>
        <input
            aria-label="feed-search-input"
            value={value}
            onChange={(event) => onChange(event.target.value)}
        />
        <button type="button" onClick={() => onSubmit(value)}>
            Submit feed search
        </button>
    </div>
));

jest.mock("../post-modal/PostModal", () => () => null);

jest.mock("../../service/PostService", () => ({
    __esModule: true,
    default: {
        createPost: jest.fn(),
    },
}));

import FeedSidebar from "./FeedSidebar";
import { StoreContext } from "../..";


beforeEach(() => {
    jest.clearAllMocks();
});


test("feed sidebar sends query to /search and keeps only recommendations/subscriptions navigation labels", () => {
    const store = { isAuthenticated: false };
    render(
        <StoreContext.Provider value={{ store }}>
            <FeedSidebar />
        </StoreContext.Provider>
    );

    expect(screen.getByText("Recommendations")).not.toBeNull();
    expect(screen.queryByText("Global")).toBeNull();
    expect(screen.queryByText("Personal")).toBeNull();

    fireEvent.change(screen.getByLabelText("feed-search-input"), {
        target: { value: "neo4j tags" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit feed search" }));

    expect(mockNavigate).toHaveBeenCalledWith("/search?q=neo4j%20tags&type=all");
});
