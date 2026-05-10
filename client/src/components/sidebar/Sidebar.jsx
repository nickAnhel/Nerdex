import { useContext } from "react";
import { Link, NavLink } from "react-router-dom"
import { observer } from "mobx-react-lite";

import "./Sidebar.css"

import { StoreContext } from "../..";
import ArticleIcon from "../icons/ArticleIcon";
import ChatIcon from "../icons/ChatIcon";
import CourseIcon from "../icons/CourseIcon";
import FeedIcon from "../icons/FeedIcon";
import LoginIcon from "../icons/LoginIcon";
import MomentsIcon from "../icons/MomentsIcon";
import PeopleIcon from "../icons/PeopleIcon";
import VideoIcon from "../icons/VideoIcon";
import { getAvatarRenderKey, getAvatarUrl } from "../../utils/avatar";


function Sidebar() {
    const { store } = useContext(StoreContext);
    const avatarSrc = getAvatarUrl(store.user, "small");
    const avatarRenderKey = getAvatarRenderKey(store.user, "small");

    return (
        <div id="sidebar">
            <div id="sidebar-top">
                <NavLink to="/people" className="sidebar-item" >
                    <PeopleIcon />
                    People
                </NavLink>
                <NavLink to="/feed" className="sidebar-item">
                    <FeedIcon />
                    Feed
                </NavLink>
                <NavLink to="/articles" className="sidebar-item">
                    <ArticleIcon />
                    Articles
                </NavLink>
                <NavLink to="/videos" className="sidebar-item">
                    <VideoIcon />
                    Videos
                </NavLink>
                <NavLink to="/moments" className="sidebar-item">
                    <MomentsIcon />
                    Moments
                </NavLink>
                <NavLink to="/courses" className="sidebar-item">
                    <CourseIcon />
                    Courses
                </NavLink>
                <NavLink to="/chats" className="sidebar-item">
                    <ChatIcon />
                    Chats
                </NavLink>
            </div>

            <div id="sidebar-bottom">
                {/* <NavLink to="/settings" className="sidebar-item">
                    <img src="/assets/settings.svg" alt="Settings" />
                </NavLink> */}

                {
                    store.isAuthenticated
                        ?
                        <Link to="/profile" className="sidebar-item">
                            <img
                                key={avatarRenderKey}
                                className="profile"
                                src={avatarSrc}
                                onError={(e) => { e.currentTarget.src = "/assets/profile.svg"; }}
                                alt="Profile"
                            />
                        </Link>
                        :
                        <Link to="/login" className="sidebar-item">
                            <LoginIcon />
                        </Link>
                }
            </div>
        </div>
    );
}

export default observer(Sidebar);
