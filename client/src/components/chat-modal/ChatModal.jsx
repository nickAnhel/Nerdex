import { useEffect, useState } from "react";

import "./ChatModal.css"

import Modal from "../modal/Modal";
import Loader from "../loader/Loader";
import UserService from "../../service/UserService";


function ChatModal({
    active,
    setActive,

    chatId,
    title,
    isPrivate,
    setTitle,
    saveChatFunc,
    onSaved,

    modalHeader,
    buttonText
}) {
    const [chatTitle, setChatTitle] = useState(title || "");
    const [isLoadingSaveChat, setIsLoadingSaveChat] = useState(false);

    const [chatIsPrivate, setChatIsPrivate] = useState(isPrivate);
    const [memberQuery, setMemberQuery] = useState("");
    const [memberResults, setMemberResults] = useState([]);
    const [selectedMembers, setSelectedMembers] = useState([]);
    const [isLoadingMembers, setIsLoadingMembers] = useState(false);
    const canEditMembers = !chatId;

    useEffect(() => {
        setChatTitle(title || "");
        setChatIsPrivate(Boolean(isPrivate));
        if (active && !chatId) {
            setMemberQuery("");
            setMemberResults([]);
            setSelectedMembers([]);
        }
    }, [active, chatId, title, isPrivate]);

    useEffect(() => {
        if (!active || !canEditMembers || memberQuery.trim().length < 1) {
            setMemberResults([]);
            return;
        }

        const timeout = setTimeout(async () => {
            setIsLoadingMembers(true);
            try {
                const res = await UserService.searchUsers({
                    query: memberQuery.trim(),
                    offset: 0,
                    limit: 6,
                });
                setMemberResults(res.data);
            } catch (e) {
                console.log(e);
                setMemberResults([]);
            } finally {
                setIsLoadingMembers(false);
            }
        }, 250);

        return () => clearTimeout(timeout);
    }, [active, canEditMembers, memberQuery]);

    const addMember = (user) => {
        if (selectedMembers.some((member) => member.user_id === user.user_id)) {
            return;
        }

        setSelectedMembers((members) => [...members, user]);
        setMemberQuery("");
        setMemberResults([]);
    }

    const removeMember = (userId) => {
        setSelectedMembers((members) => members.filter((member) => member.user_id !== userId));
    }

    const handleSaveChat = async (event) => {
        setIsLoadingSaveChat(true);
        event.preventDefault();

        try {
            const chatData = {
                chat_type: "group",
                title: chatTitle,
                is_private: chatIsPrivate,
                members: selectedMembers.map((member) => member.user_id),
            }
            const res = await saveChatFunc(chatId, chatData);

            if (setTitle) {
                setTitle(chatTitle);
            }

            if (onSaved) {
                onSaved(res?.data);
            }

        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);

        } finally {
            setIsLoadingSaveChat(false);
            setActive(false);
        }
    }

    return (
        <Modal active={active} setActive={setActive}>
            <form id="save-chat-form">
                <h1>{modalHeader}</h1>

                <input
                    type="text"
                    placeholder="Chat title"
                    value={chatTitle}
                    onChange={(e) => setChatTitle(e.target.value)}
                />

                <div className="chat-private">
                    <input
                        type="checkbox"
                        id="private"
                        name="private"
                        value="1"
                        required
                        checked={chatIsPrivate}
                        onChange={(e) => setChatIsPrivate(e.target.checked)}
                    />
                    <label htmlFor="private" className="chat">Private</label>
                </div>

                {
                    canEditMembers &&
                    <div className="chat-members-picker">
                        <input
                            type="text"
                            placeholder="Search users"
                            value={memberQuery}
                            onChange={(e) => setMemberQuery(e.target.value)}
                        />

                        {
                            selectedMembers.length > 0 &&
                            <div className="selected-members">
                                {selectedMembers.map((member) => (
                                    <button
                                        key={member.user_id}
                                        type="button"
                                        className="selected-member"
                                        onClick={() => removeMember(member.user_id)}
                                    >
                                        {member.username}
                                    </button>
                                ))}
                            </div>
                        }

                        {
                            (isLoadingMembers || memberResults.length > 0) &&
                            <div className="member-results">
                                {isLoadingMembers && <div className="member-result muted">Searching...</div>}
                                {!isLoadingMembers && memberResults.map((user) => (
                                    <button
                                        key={user.user_id}
                                        type="button"
                                        className="member-result"
                                        onClick={() => addMember(user)}
                                        disabled={selectedMembers.some((member) => member.user_id === user.user_id)}
                                    >
                                        {user.username}
                                    </button>
                                ))}
                            </div>
                        }
                    </div>
                }

                <button
                    className="btn btn-primary btn-block"
                    disabled={chatTitle.trim().length < 1}
                    onClick={(e) => { handleSaveChat(e); }}
                >
                    {isLoadingSaveChat ? <Loader /> : buttonText}
                </button>
            </form>
        </Modal>
    )
}

export default ChatModal;
