import { useEffect, useState, useRef, useContext } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { io } from "socket.io-client";

import "./ChatDetails.css"

import { StoreContext } from "../..";
import ChatService from "../../service/ChatService";

import NotFound from "../not-found/NotFound";

import Message from "../message/Message";
import Event from "../event/Event";

import ChatModal from "../chat-modal/ChatModal";


function getMaxCharsInLine(textarea, content) {
    const context = document.createElement('canvas').getContext('2d');
    const computedStyle = window.getComputedStyle(textarea);
    context.font = computedStyle.font;
    const width = context.measureText(content).width / content.length;
    return Math.floor(textarea.clientWidth / width);
}


function ChatDetails() {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();

    const params = useParams();

    const [isEditChatModalActive, setIsEditChatModalActive] = useState(false);

    const [isError, setIsError] = useState(false);

    const [chat, setChat] = useState({});

    const [chatItems, setChatItems] = useState([]);
    const [message, setMessage] = useState([]);
    const [isFirstRender, setIsFirstRender] = useState(true);

    const socket = useRef(null);
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);

    useEffect(() => {
        const fetchChat = async () => {
            try {
                const chatId = params.chatId.slice(1);
                if (!chatId) {
                    setIsError(true);
                    return;
                }

                const res = await ChatService.getChatById(chatId);

                setChat(res.data);

            } catch (e) {
                console.log(e);
                setIsError(true);
            }
        }

        fetchChat();
    }, [params.chatId])


    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scroll({
                top: messagesEndRef.current.scrollHeight,
                behavior: isFirstRender ? 'auto' : 'smooth',
            });

            setIsFirstRender(false);
        }
    }, [isFirstRender, chatItems]);

    useEffect(() => {
        const checkJoinedWrapper = async () => {
            try {
                const chatId = params.chatId.slice(1);
                if (!chatId) {
                    setIsError(true);
                    return;
                }

                const joined = await ChatService.getUserJoinedChats({ user_id: store.user.user_id });
                const isJoined = joined.data.some((ch) => ch.chat_id === chatId);

                if (isJoined) {
                    document.getElementById("chat-footer").classList.remove("hidden");
                    document.getElementById("join-btn").classList.add("hidden");
                } else {
                    document.getElementById("chat-footer").classList.add("hidden");
                    document.getElementById("join-btn").classList.remove("hidden");
                }
            } catch (e) {
                console.log(e);
                setIsError(true);
            }
        }

        checkJoinedWrapper();
    }, [store.user, chat])

    useEffect(() => {
        const getHistoryWrapper = async () => {
            try {
                clearChat();

                const chatId = params.chatId.slice(1);
                if (!chatId) {
                    setIsError(true);
                    return;
                }

                const items = await ChatService.getChatHistory(chatId);
                items.data.forEach(
                    (item) => {
                        if (item.item_type == "message") {
                            let sender = item.user_id == store.user.user_id ? "You" : item.user.username;
                            addMessageToChat(item.user_id, item.content, sender, item.created_at);

                        } else if (item.item_type == "event") {
                            switch (item.event_type) {
                                case "joined":
                                    addEventToChat(item.event_type, item.user.username, null);
                                    break;
                                case "leaved":
                                    addEventToChat(item.event_type, item.user.username, null);
                                    break;
                                case "created":
                                    addEventToChat(item.event_type, item.user.username, null);
                                    break;
                                case "added":
                                    addEventToChat(item.event_type, item.user.username, item.altered_user.username);
                                    break;
                                case "removed":
                                    addEventToChat(item.event_type, item.user.username, item.altered_user.username);
                                    break;
                            }
                        }
                    }
                );

                setIsFirstRender(true);
            } catch (e) {
                console.log(e);
                setIsError(true);
            }
        }

        getHistoryWrapper();
    }, [chat, store.user]);

    useEffect(() => {
        socket.current = io("ws://localhost:8000", {
            path: "/ws",
            transports: ["websocket"],
            upgrade: false,
        });

        socket.current.emit("join", {
            chat_id: chat.chat_id,
        })

        socket.current.on("message", (data) => {
            let msgData = JSON.parse(data);
            let sender = msgData.user_id == store.user.user_id ? "You" : msgData.username;
            addMessageToChat(msgData.user_id, msgData.content, sender, msgData.created_at);
        })

        return () => {
            socket.current.emit("leave", {
                chat_id: chat.chat_id,
            });
        }
    }, [chat, store.user]);

    const resizeTextarea = () => {
        let rowsTotalHeight = textareaRef.current.value.split("\n").length * 25;
        let symbolsTotalLength = Math.max(
            Math.ceil(textareaRef.current.value.length / getMaxCharsInLine(textareaRef.current, textareaRef.current.value)), 1
        ) * 25;

        textareaRef.current.style.height = `${Math.min(
            symbolsTotalLength ? Math.max(rowsTotalHeight, symbolsTotalLength) : rowsTotalHeight,
            200
        )
            }px`;

        messagesEndRef.current.scroll({
            top: messagesEndRef.current.scrollHeight,
            behavior: 'smooth',
        });
    }

    const clearChat = () => {
        setChatItems([]);
    }

    const addMessageToChat = (userId, msg, sender, createdAt) => {
        setChatItems(items => [...items, {
            type: "message",
            userId: userId,
            content: msg,
            username: sender,
            createdAt: createdAt
        }]);
    }

    const addEventToChat = (action, username, addedUserUsername) => {
        setChatItems(items => [...items, {
            type: "event",
            action: action,
            username: username,
            addedUserUsername: addedUserUsername
        }]);
    }

    const sendMessage = (event) => {
        if (message.trim() != "") {
            document.getElementById("message-input").value = "";

            let now = new Date();
            addMessageToChat(store.user.user_id, message.trim(), "You", now);

            let msgData = {
                chat_id: chat.chat_id,
                user_id: store.user.user_id,
                content: message.trim(),
                created_at: new Date()
            }

            socket.current.emit("message", msgData);

            setMessage("");
            textareaRef.current.value = "";
        } else {
            textareaRef.current.focus()
        }
    }

    const handleKeyDown = (event) => {
        if (event.shiftKey && event.key === 'Enter' && message.trim() != "") {
            return;
        }
        else if (event.key === 'Enter' && message.trim() != "") {
            sendMessage(message);
            event.preventDefault();
            resizeTextarea();
        }
    };

    const handleChatJoin = async () => {
        try {
            await ChatService.joinChat(chat.chat_id);
            navigate("/chats");

        } catch (e) {
            console.log(e);
        }
    }

    const handleChatLeave = async () => {
        try {
            await ChatService.leaveChat(chat.chat_id);
            navigate("/chats");

        } catch (e) {
            console.log(e);
        }
    }

    const optionsHandler = () => {
        const button = document.getElementById('options-btn');
        const menu = document.getElementById('options');
        const rect = button.getBoundingClientRect();
        // menu.style.top = `${rect.bottom + 20}px`;
        menu.style.display = (menu.style.display === 'none' || menu.style.display === '') ? 'flex' : 'none';
    }

    const handleChatDelete = async () => {
        try {
            await ChatService.deleteChat(chat.chat_id);
            navigate("/chats");
        } catch (e) {
            console.log(e);
        }
    }

    const setTitle = (newTitle) => {
        setChat((prev) => ({
            ...prev,
            title: newTitle,
        }))
    }

    if (isError) {
        return (
            <div className="chat-details">
                <NotFound />
            </div>
        )
    }

    return (
        <div className="chat-details">
            <div className="chat-header">
                <div className="header-label">
                    <img src="../../../assets/chat.svg" alt="" />
                    <h2><span id="ws-id">{chat.title}</span></h2>
                </div>

                <div className="header-actions">
                    <img id="options-btn" src="../../../assets/options.svg" alt="Options" onClick={optionsHandler} />
                </div>
            </div>
            <div id="options">
                {
                    store.user.user_id == chat.owner_id &&
                    <>
                        <div className="option" onClick={() => setIsEditChatModalActive(true)}>
                            <img src="../../../assets/edit.svg" alt="Edit" />
                            <div>Edit info</div>
                        </div>
                        <hr />
                    </>
                }
                <div className="option danger" onClick={handleChatLeave}>
                    <img src="../../../assets/leave.svg" alt="Leave" />
                    <div>Leave chat</div>
                </div>
                {
                    store.user.user_id == chat.owner_id &&
                    <div className="option danger" onClick={handleChatDelete}>
                        <img src="../../../assets/delete.svg" alt="Delete" />
                        <div>Delete chat</div>
                    </div>
                }
            </div>

            <div className="chat-body" ref={messagesEndRef}>
                {
                    chatItems.map((item, index) => {
                        if (item.type == "message") {
                            return (
                                <Message key={index} userId={item.userId} username={item.username} content={item.content} createdAt={item.createdAt} />
                            )
                        } else if (item.type == "event") {
                            return (
                                <Event key={index} action={item.action} username={item.username} addedUserUsername={item.addedUserUsername} />
                            )
                        }
                    })
                }
            </div>

            <div id="chat-footer" className="chat-footer">
                <div className="msg-box">
                    <textarea
                        name="message-input"
                        ref={textareaRef}
                        value={message}
                        placeholder="Type a message"
                        onChange={(e) => { setMessage(e.target.value); resizeTextarea() }}
                        id="message-input"
                        onKeyDown={handleKeyDown}
                    >
                    </textarea>
                </div>
                <button onClick={sendMessage}>
                    <img src="../../../assets/send-message.svg" alt="" />
                </button>
            </div>
            <button id="join-btn" className="hidden" onClick={handleChatJoin}>Join</button>

            <ChatModal
                key={"edit"}
                active={isEditChatModalActive}
                setActive={setIsEditChatModalActive}
                saveChatFunc={ChatService.updateChat}
                chatId={chat.chat_id}
                title={chat.title}
                setTitle={setTitle}
                isPrivate={chat.is_private}
                modalHeader={"Edit chat info"}
                buttonText={"Save"}
            />
        </div>
    )
}

export default ChatDetails;