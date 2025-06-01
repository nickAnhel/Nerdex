import { useState, useContext } from "react";

import "./ChatSidebar.css";

import { StoreContext } from "../..";
import ChatService from "../../service/ChatService";

import ChatModal from "../chat-modal/ChatModal";

import ChatList from "../../components/chat-list/ChatList";


function Chats() {
    const [isCreateChatActive, setIsCreateChatActive] = useState(false);

    const [query, setQuery] = useState();
    const [isSearch, setIsSearch] = useState(false);

    const handleClear = () => {
        setQuery("");
        setIsSearch(false);
    }

    return (
        <div id="chat-sidebar">
            <div id="search">
                <div className={"search-bar" + (isSearch ? " active" : "")}>
                    <input
                        id="search-input"
                        type="text"
                        placeholder="Search"
                        value={query}
                        maxLength={50}
                        onFocus={() => setIsSearch(true)}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                    <div className="search-actions">
                        <button
                            className={query || isSearch ? "show search-btn" : "search-btn hidden"}
                            onClick={handleClear}
                        >
                            <img
                                className="close"
                                src="../../../assets/clear.svg"
                                alt="Clear"
                            />
                        </button>
                    </div>
                </div>
            </div>

            <button
                className="create-chat"
                onClick={() => setIsCreateChatActive(true)}
            >
                Create chat
            </button>

            {
                isSearch ?
                    <ChatList fetchChats={ChatService.searchChats} filters={{ query: query }} refresh={query} />
                    :
                    <ChatList fetchChats={ChatService.getUserJoinedChats} refresh={isSearch} />
            }

            <ChatModal
                key={"create"}
                active={isCreateChatActive}
                setActive={setIsCreateChatActive}
                saveChatFunc={ChatService.createChat}
                modalHeader={"Create new chat"}
                buttonText={"Create chat"}
            />
        </div>
    )
}

export default Chats;