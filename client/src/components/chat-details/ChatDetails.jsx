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

function createClientMessageId() {
    if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
    }

    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function parseSocketPayload(data) {
    return typeof data === "string" ? JSON.parse(data) : data;
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
    }, [params.chatId, store.user, chat])

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
                        if (item.item_type === "message") {
                            addMessageToChat({
                                messageId: item.message_id,
                                clientMessageId: item.client_message_id,
                                userId: item.user_id,
                                content: item.content,
                                username: item.user_id === store.user.user_id ? "You" : item.user.username,
                                createdAt: item.created_at,
                                avatarUrl: item.user?.avatar?.small_url || null,
                                status: "sent",
                            });

                        } else if (item.item_type === "event") {
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
                                default:
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
    }, [params.chatId, chat, store.user]);

    useEffect(() => {
        if (!chat.chat_id) {
            return;
        }

        socket.current = io(process.env.REACT_APP_WS_HOST, {
            path: "/ws",
            transports: ["websocket"],
            upgrade: false,
            auth: {
                token: localStorage.getItem("token"),
            },
        });

        socket.current.on("connect_error", (error) => {
            console.log(error);
            setIsError(true);
        });

        socket.current.emit("join", {
            chat_id: chat.chat_id,
        }, (response) => {
            if (response && !response.ok) {
                console.log(response.error?.detail || "Failed to join chat");
            }
        });

        socket.current.on("message:created", (data) => {
            const msgData = parseSocketPayload(data);
            addMessageToChat({
                messageId: msgData.message_id,
                clientMessageId: msgData.client_message_id,
                userId: msgData.user_id,
                content: msgData.content,
                username: msgData.user_id === store.user.user_id ? "You" : msgData.username,
                createdAt: msgData.created_at,
                avatarUrl: msgData.avatar_small_url || null,
                status: "sent",
            });
        })

        return () => {
            socket.current.emit("leave", {
                chat_id: chat.chat_id,
            });
            socket.current.off("message:created");
            socket.current.off("connect_error");
            socket.current.disconnect();
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

    const addMessageToChat = (messageItem) => {
        const nextItem = {
            type: "message",
            ...messageItem,
        };

        setChatItems(items => {
            const existingIndex = items.findIndex((item) => (
                item.type === "message" &&
                (
                    (nextItem.messageId && item.messageId === nextItem.messageId) ||
                    (nextItem.clientMessageId && item.clientMessageId === nextItem.clientMessageId)
                )
            ));

            if (existingIndex === -1) {
                return [...items, nextItem];
            }

            return items.map((item, index) => index === existingIndex ? { ...item, ...nextItem } : item);
        });
    }

    const addEventToChat = (action, username, addedUserUsername) => {
        setChatItems(items => [...items, {
            type: "event",
            action: action,
            username: username,
            addedUserUsername: addedUserUsername
        }]);
    }

    const markMessageFailed = (clientMessageId) => {
        setChatItems(items => items.map((item) => (
            item.type === "message" && item.clientMessageId === clientMessageId
                ? { ...item, status: "failed" }
                : item
        )));
    }

    const sendMessagePayload = (pendingMessage) => {
        socket.current.timeout(10000).emit("message", {
            chat_id: chat.chat_id,
            client_message_id: pendingMessage.clientMessageId,
            content: pendingMessage.content,
        }, (error, response) => {
            if (error || !response || !response.ok) {
                console.log(response?.error?.detail || "Failed to send message");
                markMessageFailed(pendingMessage.clientMessageId);
                return;
            }

            const msgData = response.data;
            addMessageToChat({
                messageId: msgData.message_id,
                clientMessageId: msgData.client_message_id,
                userId: msgData.user_id,
                content: msgData.content,
                username: "You",
                createdAt: msgData.created_at,
                avatarUrl: msgData.avatar_small_url || null,
                status: "sent",
            });
        });
    }

    const retryMessage = (clientMessageId) => {
        const failedMessage = chatItems.find((item) => (
            item.type === "message" && item.clientMessageId === clientMessageId
        ));
        if (!failedMessage) {
            return;
        }

        addMessageToChat({ ...failedMessage, status: "pending" });
        sendMessagePayload(failedMessage);
    }

    const sendMessage = () => {
        const trimmedMessage = message.trim();
        if (trimmedMessage !== "") {
            const pendingMessage = {
                clientMessageId: createClientMessageId(),
                userId: store.user.user_id,
                content: trimmedMessage,
                username: "You",
                createdAt: new Date().toISOString(),
                avatarUrl: store.user?.avatar?.small_url || null,
                status: "pending",
            };

            addMessageToChat(pendingMessage);
            sendMessagePayload(pendingMessage);

            setMessage("");
            textareaRef.current.value = "";
        } else {
            textareaRef.current.focus()
        }
    }

    const handleKeyDown = (event) => {
        if (event.shiftKey && event.key === 'Enter' && message.trim() !== "") {
            return;
        }
        else if (event.key === 'Enter' && message.trim() !== "") {
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
        const menu = document.getElementById('options');
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
                    store.user.user_id === chat.owner_id &&
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
                    store.user.user_id === chat.owner_id &&
                    <div className="option danger" onClick={handleChatDelete}>
                        <img src="../../../assets/delete.svg" alt="Delete" />
                        <div>Delete chat</div>
                    </div>
                }
            </div>

            <div className="chat-body" ref={messagesEndRef}>
                {
                    chatItems.map((item, index) => {
                        if (item.type === "message") {
                            return (
                                <Message
                                    key={index}
                                    userId={item.userId}
                                    username={item.username}
                                    content={item.content}
                                    createdAt={item.createdAt}
                                    avatarUrl={item.avatarUrl}
                                    status={item.status}
                                    onRetry={() => retryMessage(item.clientMessageId)}
                                />
                            )
                        } else if (item.type === "event") {
                            return (
                                <Event key={index} action={item.action} username={item.username} addedUserUsername={item.addedUserUsername} />
                            )
                        }

                        return null;
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
                <button className="btn btn-primary" onClick={sendMessage}>
                    <img src="../../../assets/send-message.svg" alt="" />
                </button>
            </div>
            <button id="join-btn" className="btn btn-primary hidden" onClick={handleChatJoin}>Join</button>

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
