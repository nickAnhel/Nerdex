import { useCallback, useEffect, useState, useRef, useContext } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { io } from "socket.io-client";

import "./ChatDetails.css"

import { StoreContext } from "../..";
import AssetService from "../../service/AssetService";
import ChatService from "../../service/ChatService";

import NotFound from "../not-found/NotFound";

import Message from "../message/Message";
import Event from "../event/Event";

import ChatModal from "../chat-modal/ChatModal";
import Modal from "../modal/Modal";
import { getAvatarUrl } from "../../utils/avatar";
import {
    buildComposerAttachmentFromAsset,
    formatAttachmentSize,
    resolveAssetTypeForFile,
} from "../../utils/postAttachments";


const HISTORY_PAGE_SIZE = 50;


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

function normalizeTimelineItem(item, currentUserId) {
    if (item.item_type === "message") {
        return {
            type: "message",
            key: `message-${item.message_id || item.client_message_id}`,
            chatSeq: item.chat_seq,
            messageId: item.message_id,
            clientMessageId: item.client_message_id,
            userId: item.user_id,
            content: item.content,
            editedAt: item.edited_at,
            deletedAt: item.deleted_at,
            deletedBy: item.deleted_by,
            replyToMessageId: item.reply_to_message_id,
            replyPreview: normalizeReplyPreview(item.reply_preview),
            username: item.user_id === currentUserId ? "You" : item.user.username,
            createdAt: item.created_at,
            avatarUrl: item.user?.avatar?.small_url || null,
            attachments: normalizeMessageAttachments(item.attachments),
            status: "sent",
        };
    }

    if (item.item_type === "event") {
        return {
            type: "event",
            key: `event-${item.event_id}`,
            chatSeq: item.chat_seq,
            eventId: item.event_id,
            action: item.event_type,
            username: item.user.username,
            addedUserUsername: item.altered_user?.username || null,
        };
    }

    return null;
}

function normalizeReplyPreview(replyPreview) {
    if (!replyPreview) {
        return null;
    }

    return {
        messageId: replyPreview.message_id,
        senderDisplayName: replyPreview.sender_display_name,
        contentPreview: replyPreview.content_preview,
        deleted: replyPreview.deleted,
    };
}

function sortTimelineItems(items) {
    return [...items].sort((a, b) => {
        if (a.chatSeq == null && b.chatSeq == null) {
            return 0;
        }
        if (a.chatSeq == null) {
            return 1;
        }
        if (b.chatSeq == null) {
            return -1;
        }
        return a.chatSeq - b.chatSeq;
    });
}

function mergeTimelineItems(prevItems, nextItems) {
    const byKey = new Map();

    [...prevItems, ...nextItems].forEach((item) => {
        const keys = [
            item.key,
            item.messageId ? `message-${item.messageId}` : null,
            item.clientMessageId ? `client-message-${item.clientMessageId}` : null,
            item.eventId ? `event-${item.eventId}` : null,
        ].filter(Boolean);

        const existingKey = keys.find((key) => byKey.has(key));
        if (existingKey) {
            const merged = {
                ...byKey.get(existingKey),
                ...item,
            };
            keys.forEach((key) => byKey.set(key, merged));
            return;
        }

        keys.forEach((key) => byKey.set(key, item));
    });

    return sortTimelineItems(Array.from(new Set(byKey.values())));
}

function getTimelineBounds(items) {
    const seqs = items
        .map((item) => item.chatSeq)
        .filter((chatSeq) => chatSeq != null);

    if (seqs.length === 0) {
        return {
            oldestSeq: null,
            latestSeq: null,
        };
    }

    return {
        oldestSeq: Math.min(...seqs),
        latestSeq: Math.max(...seqs),
    };
}

function normalizeMessagePayload(msgData, currentUserId) {
    return {
        messageId: msgData.message_id,
        clientMessageId: msgData.client_message_id,
        chatSeq: msgData.chat_seq,
        userId: msgData.user_id,
        content: msgData.content,
        editedAt: msgData.edited_at,
        deletedAt: msgData.deleted_at,
        deletedBy: msgData.deleted_by,
        replyToMessageId: msgData.reply_to_message_id,
        replyPreview: normalizeReplyPreview(msgData.reply_preview),
        username: msgData.user_id === currentUserId ? "You" : msgData.username,
        createdAt: msgData.created_at,
        avatarUrl: msgData.avatar_small_url || null,
        attachments: normalizeMessageAttachments(msgData.attachments),
        status: "sent",
    };
}

function normalizeMessageAttachments(attachments = []) {
    return attachments.map((attachment) => ({
        asset_id: attachment.asset_id,
        asset_type: attachment.asset_type,
        mime_type: attachment.mime_type,
        file_kind: attachment.file_kind || "file",
        original_filename: attachment.original_filename || "Untitled file",
        size_bytes: attachment.size_bytes,
        preview_url: attachment.preview_url,
        original_url: attachment.original_url,
        poster_url: attachment.poster_url,
        download_url: attachment.download_url,
        stream_url: attachment.stream_url,
        is_audio: Boolean(attachment.is_audio),
        duration_ms: attachment.duration_ms || null,
        position: attachment.position || 0,
        uploadState: "ready",
    }));
}

function buildReplyPreviewFromMessage(messageItem) {
    return {
        messageId: messageItem.messageId,
        senderDisplayName: messageItem.username,
        contentPreview: messageItem.deletedAt ? "Message deleted" : messageItem.content,
        deleted: Boolean(messageItem.deletedAt),
    };
}


function ChatDetails() {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();

    const params = useParams();

    const [isEditChatModalActive, setIsEditChatModalActive] = useState(false);

    const [isError, setIsError] = useState(false);

    const [chat, setChat] = useState({});

    const [chatItems, setChatItems] = useState([]);
    const [message, setMessage] = useState("");
    const [attachments, setAttachments] = useState([]);
    const [editingMessage, setEditingMessage] = useState(null);
    const [replyingToMessage, setReplyingToMessage] = useState(null);
    const [messageMenu, setMessageMenu] = useState(null);
    const [deleteMessageCandidate, setDeleteMessageCandidate] = useState(null);
    const [isDeletingMessage, setIsDeletingMessage] = useState(false);
    const [oldestSeq, setOldestSeq] = useState(null);
    const [, setLatestSeq] = useState(null);
    const [hasMoreHistory, setHasMoreHistory] = useState(true);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);

    const socket = useRef(null);
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);
    const fileInputRef = useRef(null);
    const latestSeqRef = useRef(null);
    const pendingPrependScrollRef = useRef(null);
    const shouldScrollBottomRef = useRef(false);
    const directMember = chat.chat_type === "direct"
        ? chat.members?.find((member) => member.user_id !== store.user.user_id)
        : null;
    const chatTitle = directMember?.username || chat.title;
    const chatImage = directMember ? getAvatarUrl(directMember, "small") : "../../../assets/chat.svg";

    const markCurrentChatRead = useCallback(async (chatId) => {
        try {
            await ChatService.markChatRead(chatId);
        } catch (e) {
            console.log(e);
        }
    }, []);

    const applyHistoryItems = useCallback((items, { prepend = false, scrollToBottom = false } = {}) => {
        const normalizedItems = items
            .map((item) => normalizeTimelineItem(item, store.user.user_id))
            .filter(Boolean);

        if (prepend && messagesEndRef.current) {
            pendingPrependScrollRef.current = {
                scrollHeight: messagesEndRef.current.scrollHeight,
                scrollTop: messagesEndRef.current.scrollTop,
            };
        }

        shouldScrollBottomRef.current = scrollToBottom;
        setChatItems((prevItems) => mergeTimelineItems(prevItems, normalizedItems));
    }, [store.user.user_id]);

    const updateMessageInChat = useCallback((messageItem) => {
        setChatItems(items => items.map((item) => (
            item.type === "message" && item.messageId === messageItem.messageId
                ? {
                    ...item,
                    ...messageItem,
                    key: item.key,
                }
                : item.type === "message" && item.replyToMessageId === messageItem.messageId
                    ? {
                        ...item,
                        replyPreview: buildReplyPreviewFromMessage(messageItem),
                    }
                    : item
        )));
    }, []);

    useEffect(() => {
        const bounds = getTimelineBounds(chatItems);
        setOldestSeq(bounds.oldestSeq);
        setLatestSeq(bounds.latestSeq);
        latestSeqRef.current = bounds.latestSeq;

        if (pendingPrependScrollRef.current && messagesEndRef.current) {
            const previousScroll = pendingPrependScrollRef.current;
            pendingPrependScrollRef.current = null;
            requestAnimationFrame(() => {
                if (!messagesEndRef.current) {
                    return;
                }
                messagesEndRef.current.scrollTop =
                    messagesEndRef.current.scrollHeight -
                    previousScroll.scrollHeight +
                    previousScroll.scrollTop;
            });
            return;
        }

        if (shouldScrollBottomRef.current && messagesEndRef.current) {
            shouldScrollBottomRef.current = false;
            requestAnimationFrame(() => {
                if (!messagesEndRef.current) {
                    return;
                }
                messagesEndRef.current.scroll({
                    top: messagesEndRef.current.scrollHeight,
                    behavior: 'auto',
                });
            });
        }
    }, [chatItems]);

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
        if (!chat.chat_id) {
            return;
        }

        markCurrentChatRead(chat.chat_id);
    }, [chat.chat_id, markCurrentChatRead]);

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
                const chatFooter = document.getElementById("chat-footer");
                const joinButton = document.getElementById("join-btn");

                if (isJoined || chat.chat_type === "direct") {
                    chatFooter?.classList.remove("hidden");
                    joinButton?.classList.add("hidden");
                } else {
                    chatFooter?.classList.add("hidden");
                    joinButton?.classList.remove("hidden");
                }
            } catch (e) {
                console.log(e);
                setIsError(true);
            }
        }

        checkJoinedWrapper();
    }, [params.chatId, store.user, chat])

    const loadOlderHistory = useCallback(async () => {
        if (!chat.chat_id || oldestSeq == null || isLoadingHistory || !hasMoreHistory) {
            return;
        }

        try {
            setIsLoadingHistory(true);
            const res = await ChatService.getChatHistory(chat.chat_id, {
                before_seq: oldestSeq,
                limit: HISTORY_PAGE_SIZE,
            });

            if (res.data.length < HISTORY_PAGE_SIZE) {
                setHasMoreHistory(false);
            }

            applyHistoryItems(res.data, { prepend: true });
        } catch (e) {
            console.log(e);
            setIsError(true);
        } finally {
            setIsLoadingHistory(false);
        }
    }, [applyHistoryItems, chat.chat_id, hasMoreHistory, isLoadingHistory, oldestSeq]);

    const handleHistoryScroll = useCallback(() => {
        if (messagesEndRef.current?.scrollTop === 0) {
            loadOlderHistory();
        }
    }, [loadOlderHistory]);

    useEffect(() => {
        const getHistoryWrapper = async () => {
            try {
                clearChat();
                setOldestSeq(null);
                setLatestSeq(null);
                latestSeqRef.current = null;
                setHasMoreHistory(true);

                const chatId = params.chatId.slice(1);
                if (!chatId) {
                    setIsError(true);
                    return;
                }

                const items = await ChatService.getChatHistory(chatId, {
                    limit: HISTORY_PAGE_SIZE,
                });

                setHasMoreHistory(items.data.length >= HISTORY_PAGE_SIZE);
                applyHistoryItems(items.data, { scrollToBottom: true });
            } catch (e) {
                console.log(e);
                setIsError(true);
            }
        }

        getHistoryWrapper();
    }, [applyHistoryItems, params.chatId]);

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

        const syncMissedItems = async () => {
            if (latestSeqRef.current == null) {
                return;
            }

            try {
                const res = await ChatService.getChatHistory(chat.chat_id, {
                    after_seq: latestSeqRef.current,
                    limit: HISTORY_PAGE_SIZE,
                });
                applyHistoryItems(res.data, { scrollToBottom: true });
            } catch (e) {
                console.log(e);
            }
        };

        socket.current.on("connect", () => {
            socket.current.emit("join", {
                chat_id: chat.chat_id,
            }, (response) => {
                if (response && !response.ok) {
                    console.log(response.error?.detail || "Failed to join chat");
                    return;
                }
                syncMissedItems();
            });
        });

        socket.current.on("connect_error", (error) => {
            console.log(error);
            setIsError(true);
        });

        socket.current.on("message:created", (data) => {
            const msgData = parseSocketPayload(data);
            addMessageToChat(normalizeMessagePayload(msgData, store.user.user_id));
            markCurrentChatRead(msgData.chat_id);
        })

        socket.current.on("message:updated", (data) => {
            const msgData = parseSocketPayload(data);
            updateMessageInChat(normalizeMessagePayload(msgData, store.user.user_id));
        })

        socket.current.on("message:deleted", (data) => {
            const msgData = parseSocketPayload(data);
            updateMessageInChat(normalizeMessagePayload(msgData, store.user.user_id));
        })

        return () => {
            socket.current.emit("leave", {
                chat_id: chat.chat_id,
            });
            socket.current.off("connect");
            socket.current.off("message:created");
            socket.current.off("message:updated");
            socket.current.off("message:deleted");
            socket.current.off("connect_error");
            socket.current.disconnect();
        }
    }, [applyHistoryItems, chat.chat_id, markCurrentChatRead, store.user.user_id, updateMessageInChat]);

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
            key: messageItem.messageId
                ? `message-${messageItem.messageId}`
                : `client-message-${messageItem.clientMessageId}`,
            ...messageItem,
        };

        shouldScrollBottomRef.current = true;
        setChatItems(items => mergeTimelineItems(items, [nextItem]));
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
            reply_to_message_id: pendingMessage.replyToMessageId || null,
            asset_ids: pendingMessage.attachments
                .filter((attachment) => attachment.uploadState === "ready" && attachment.asset_id)
                .map((attachment) => attachment.asset_id),
        }, (error, response) => {
            if (error || !response || !response.ok) {
                console.log(response?.error?.detail || "Failed to send message");
                markMessageFailed(pendingMessage.clientMessageId);
                return;
            }

            const msgData = response.data;
            addMessageToChat(normalizeMessagePayload(msgData, store.user.user_id));
            markCurrentChatRead(msgData.chat_id);
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

    const clearComposer = () => {
        setMessage("");
        setAttachments([]);
        setEditingMessage(null);
        setReplyingToMessage(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
        if (textareaRef.current) {
            textareaRef.current.value = "";
            textareaRef.current.style.height = "25px";
        }
    }

    const updateMessage = () => {
        const trimmedMessage = message.trim();
        if (!editingMessage || trimmedMessage === "") {
            textareaRef.current.focus();
            return;
        }

        socket.current.timeout(10000).emit("message:update", {
            message_id: editingMessage.messageId,
            content: trimmedMessage,
        }, (error, response) => {
            if (error || !response || !response.ok) {
                console.log(response?.error?.detail || "Failed to update message");
                return;
            }

            updateMessageInChat(normalizeMessagePayload(response.data, store.user.user_id));
            clearComposer();
        });
    }

    const uploadAttachment = async (file) => {
        const localId = `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const pendingAttachment = {
            id: localId,
            original_filename: file.name,
            size_bytes: file.size,
            file_kind: resolveAssetTypeForFile(file),
            uploadState: "uploading",
            error: "",
        };

        setAttachments((items) => [...items, pendingAttachment]);
        try {
            const initRes = await AssetService.initUpload({
                filename: file.name,
                size_bytes: file.size,
                declared_mime_type: file.type || null,
                asset_type: resolveAssetTypeForFile(file),
                usage_context: "message_attachment",
            });
            const uploadRes = await AssetService.uploadFile(
                initRes.data.upload_url,
                file,
                initRes.data.upload_headers || {},
            );
            if (!uploadRes.ok) {
                throw new Error("Upload failed");
            }

            const finalizeRes = await AssetService.finalizeUpload(initRes.data.asset.asset_id);
            const attachment = buildComposerAttachmentFromAsset(
                finalizeRes.data.asset,
                "file",
                file.name,
            );
            setAttachments((items) => items.map((item) => (
                item.id === localId ? { ...attachment, id: localId } : item
            )));
        } catch (e) {
            console.log(e);
            setAttachments((items) => items.map((item) => (
                item.id === localId
                    ? { ...item, uploadState: "failed", error: "Upload failed" }
                    : item
            )));
        }
    }

    const handleAttachmentSelect = (event) => {
        const files = Array.from(event.target.files || []);
        files.forEach(uploadAttachment);
        event.target.value = "";
    }

    const removeAttachment = (attachmentId) => {
        setAttachments((items) => items.filter((item) => item.id !== attachmentId));
    }

    const sendMessage = () => {
        if (editingMessage) {
            updateMessage();
            return;
        }

        const trimmedMessage = message.trim();
        const readyAttachments = attachments.filter((attachment) => (
            attachment.uploadState === "ready" && attachment.asset_id
        ));
        const hasUploadingAttachments = attachments.some((attachment) => attachment.uploadState === "uploading");
        if (hasUploadingAttachments) {
            return;
        }

        if (trimmedMessage !== "" || readyAttachments.length > 0) {
            const pendingMessage = {
                clientMessageId: createClientMessageId(),
                userId: store.user.user_id,
                content: trimmedMessage,
                attachments: readyAttachments,
                replyToMessageId: replyingToMessage?.messageId || null,
                replyPreview: replyingToMessage ? buildReplyPreviewFromMessage(replyingToMessage) : null,
                username: "You",
                createdAt: new Date().toISOString(),
                avatarUrl: store.user?.avatar?.small_url || null,
                status: "pending",
            };

            addMessageToChat(pendingMessage);
            sendMessagePayload(pendingMessage);

            clearComposer();
        } else {
            textareaRef.current.focus()
        }
    }

    const handleKeyDown = (event) => {
        if (event.shiftKey && event.key === 'Enter' && message.trim() !== "") {
            return;
        }
        else if (event.key === 'Enter' && (message.trim() !== "" || attachments.length > 0)) {
            sendMessage();
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

    const openMessageMenu = (event, item) => {
        if (!item.messageId || item.status !== "sent") {
            return;
        }

        event.preventDefault();
        setMessageMenu({
            x: event.clientX,
            y: event.clientY,
            message: item,
        });
    }

    const startEditingMessage = () => {
        if (!messageMenu?.message) {
            return;
        }

        setEditingMessage(messageMenu.message);
        setReplyingToMessage(null);
        setMessage(messageMenu.message.content);
        setMessageMenu(null);
        requestAnimationFrame(() => {
            textareaRef.current?.focus();
            resizeTextarea();
        });
    }

    const requestDeleteSelectedMessage = () => {
        if (!messageMenu?.message) {
            return;
        }

        setDeleteMessageCandidate(messageMenu.message);
        setMessageMenu(null);
    }

    const startReplyingToMessage = () => {
        if (!messageMenu?.message) {
            return;
        }

        setReplyingToMessage(messageMenu.message);
        setEditingMessage(null);
        setMessageMenu(null);
        requestAnimationFrame(() => {
            textareaRef.current?.focus();
        });
    }

    const scrollToMessage = (messageId) => {
        const target = document.getElementById(`message-${messageId}`);
        if (!target) {
            return;
        }

        target.scrollIntoView({
            behavior: "smooth",
            block: "center",
        });
    }

    const closeDeleteMessageModal = () => {
        if (!isDeletingMessage) {
            setDeleteMessageCandidate(null);
        }
    }

    const deleteSelectedMessage = () => {
        if (!deleteMessageCandidate) {
            return;
        }

        const messageId = deleteMessageCandidate.messageId;
        setIsDeletingMessage(true);
        socket.current.timeout(10000).emit("message:delete", {
            message_id: messageId,
        }, (error, response) => {
            setIsDeletingMessage(false);
            if (error || !response || !response.ok) {
                console.log(response?.error?.detail || "Failed to delete message");
                return;
            }

            updateMessageInChat(normalizeMessagePayload(response.data, store.user.user_id));
            setDeleteMessageCandidate(null);
            if (editingMessage?.messageId === messageId) {
                clearComposer();
            }
        });
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
        <div className="chat-details" onClick={() => setMessageMenu(null)}>
            <div className="chat-header">
                <div className="header-label">
                    <img
                        src={chatImage}
                        alt=""
                        onError={(event) => {
                            event.currentTarget.src = "../../../assets/chat.svg";
                        }}
                    />
                    <h2><span id="ws-id">{chatTitle}</span></h2>
                </div>

                <div className="header-actions">
                    <img id="options-btn" src="../../../assets/options.svg" alt="Options" onClick={optionsHandler} />
                </div>
            </div>
            <div id="options">
                {
                    store.user.user_id === chat.owner_id && chat.chat_type !== "direct" &&
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

            <div className="chat-body" ref={messagesEndRef} onScroll={handleHistoryScroll}>
                {
                    isLoadingHistory &&
                    <div className="history-loader">Loading history...</div>
                }
                {
                    chatItems.map((item, index) => {
                        if (item.type === "message") {
                            return (
                                <Message
                                    key={item.key || index}
                                    messageId={item.messageId}
                                    userId={item.userId}
                                    username={item.username}
                                    content={item.content}
                                    createdAt={item.createdAt}
                                    avatarUrl={item.avatarUrl}
                                    status={item.status}
                                    editedAt={item.editedAt}
                                    deletedAt={item.deletedAt}
                                    replyPreview={item.replyPreview}
                                    attachments={item.attachments}
                                    onContextMenu={(event) => openMessageMenu(event, item)}
                                    onReplyPreviewClick={scrollToMessage}
                                    onRetry={() => retryMessage(item.clientMessageId)}
                                />
                            )
                        } else if (item.type === "event") {
                            return (
                                <Event key={item.key || index} action={item.action} username={item.username} addedUserUsername={item.addedUserUsername} />
                            )
                        }

                        return null;
                    })
                }
            </div>
            {
                messageMenu &&
                <div
                    className="message-context-menu"
                    style={{ left: messageMenu.x, top: messageMenu.y }}
                    onClick={(event) => event.stopPropagation()}
                >
                    <button type="button" onClick={startReplyingToMessage}>Reply</button>
                    {
                        messageMenu.message.userId === store.user.user_id && !messageMenu.message.deletedAt &&
                        <>
                            <button type="button" onClick={startEditingMessage}>Edit</button>
                            <button type="button" className="danger" onClick={requestDeleteSelectedMessage}>Delete</button>
                        </>
                    }
                </div>
            }
            <Modal active={Boolean(deleteMessageCandidate)} setActive={closeDeleteMessageModal}>
                <div className="delete-message-modal">
                    <h2>Delete message?</h2>
                    <p>The message will stay in history as a deleted message stub.</p>
                    <div className="delete-message-modal-actions">
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={closeDeleteMessageModal}
                            disabled={isDeletingMessage}
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            className="btn btn-danger"
                            onClick={deleteSelectedMessage}
                            disabled={isDeletingMessage}
                        >
                            {isDeletingMessage ? "Deleting..." : "Delete"}
                        </button>
                    </div>
                </div>
            </Modal>

            <div id="chat-footer" className="chat-footer">
                {
                    editingMessage &&
                    <div className="edit-banner">
                        <div>
                            <span>Editing message</span>
                            <p>{editingMessage.content}</p>
                        </div>
                        <button type="button" onClick={clearComposer}>Cancel</button>
                    </div>
                }
                {
                    replyingToMessage &&
                    <div className="reply-banner">
                        <div>
                            <span>Replying to {replyingToMessage.username}</span>
                            <p>{replyingToMessage.deletedAt ? "Message deleted" : replyingToMessage.content}</p>
                        </div>
                        <button type="button" onClick={() => setReplyingToMessage(null)}>Cancel</button>
                    </div>
                }
                {
                    attachments.length > 0 &&
                    <div className="composer-attachments">
                        {attachments.map((attachment) => (
                            <div
                                key={attachment.id || attachment.asset_id}
                                className={`composer-attachment composer-attachment-${attachment.uploadState}`}
                            >
                                <span className="composer-attachment-name">
                                    {attachment.original_filename || "Untitled file"}
                                </span>
                                <span className="composer-attachment-meta">
                                    {attachment.uploadState === "uploading"
                                        ? "Uploading"
                                        : attachment.uploadState === "failed"
                                            ? attachment.error || "Failed"
                                            : formatAttachmentSize(attachment.size_bytes)}
                                </span>
                                <button
                                    type="button"
                                    aria-label={`Remove ${attachment.original_filename || "attachment"}`}
                                    onClick={() => removeAttachment(attachment.id)}
                                >
                                    x
                                </button>
                            </div>
                        ))}
                    </div>
                }
                <div className="msg-box">
                    <button
                        type="button"
                        className="attach-button"
                        aria-label="Attach file"
                        disabled={Boolean(editingMessage)}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        +
                    </button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        className="attachment-input"
                        onChange={handleAttachmentSelect}
                    />
                    <textarea
                        name="message-input"
                        ref={textareaRef}
                        value={message}
                        placeholder={editingMessage ? "Edit message" : "Type a message"}
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
            {chat.chat_type !== "direct" && <button id="join-btn" className="btn btn-primary hidden" onClick={handleChatJoin}>Join</button>}

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
