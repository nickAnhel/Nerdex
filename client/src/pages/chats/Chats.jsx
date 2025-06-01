import { useContext } from "react";
import { Outlet } from "react-router-dom";

import "./Chats.css";

import { StoreContext } from "../..";

import Unauthorized from "../../components/unauthorized/Unauthorized";
import ChatSidebar from "../../components/chat-sidebar/ChatSidebar"




function Chats() {
    const { store } = useContext(StoreContext);

    if (!store.isAuthenticated) {
        return (
            <div id="chats">
                <Unauthorized />
            </div>
        )
    }

    return (
        <div id="chats">
            <ChatSidebar />
            <Outlet />
        </div>
    )
}

export default Chats;