import { render, waitFor } from "@testing-library/react";

const mockSetSearchParams = jest.fn();
let mockLocationSearch = "";

jest.mock("react-router-dom", () => ({
    Link: ({ children, to, className }) => <a href={to} className={className}>{children}</a>,
    useNavigate: () => jest.fn(),
    useSearchParams: () => [
        new URLSearchParams(mockLocationSearch),
        mockSetSearchParams,
    ],
}), { virtual: true });

jest.mock("../..", () => {
    const React = require("react");
    return {
        StoreContext: React.createContext({ store: {} }),
    };
}, { virtual: true });

jest.mock("../../components/global-search-input/GlobalSearchInput", () => () => <div />);
jest.mock("../videos/MomentsViewer", () => () => <div>Moments Viewer</div>);

import { StoreContext } from "../..";
import Moments from "./Moments";


function renderMoments({ initialSearch = "", isAuthenticated = false } = {}) {
    mockLocationSearch = initialSearch;
    const store = { isAuthenticated };
    return render(
        <StoreContext.Provider value={{ store }}>
            <Moments />
        </StoreContext.Provider>
    );
}


beforeEach(() => {
    jest.clearAllMocks();
});


test("moments page drops tab-like params and keeps deep-link moment id", async () => {
    renderMoments({ initialSearch: "tab=subscriptions&moment=moment-7" });

    await waitFor(() => {
        expect(mockSetSearchParams).toHaveBeenCalledTimes(1);
    });

    const [params, options] = mockSetSearchParams.mock.calls[0];
    expect(params.toString()).toBe("moment=moment-7");
    expect(options).toEqual({ replace: true });
});
