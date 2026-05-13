import { render, screen } from "@testing-library/react";

import ChatListItem from "./ChatListItem";

jest.mock("react-router-dom", () => ({
    NavLink: ({ children, className, to }) => (
        <a className={className} href={to}>{children}</a>
    ),
}), { virtual: true });

jest.mock("../..", () => ({
    StoreContext: require("react").createContext({
        store: { user: { user_id: "user-1" } },
    }),
}));


test("renders dialog preview time and unread count", () => {
    render(
        <ChatListItem
            chat={{
                chat_id: "chat-1",
                chat_type: "group",
                title: "Study group",
                display_title: "Study group",
                last_message: {
                    content: "Latest update",
                    created_at: "2026-05-12T10:00:00Z",
                },
                last_message_at: "2026-05-12T10:00:00Z",
                unread_count: 2,
                members: [],
            }}
        />
    );

    expect(screen.getByText("Study group")).toBeTruthy();
    expect(screen.getByText("Latest update")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();
});
