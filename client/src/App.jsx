import { useEffect, useContext } from "react";
import { Outlet, RouterProvider, createBrowserRouter } from "react-router-dom";
import { observer } from "mobx-react-lite";

import "./App.css";

import { StoreContext } from ".";

import Sidebar from "./components/sidebar/Sidebar";
import Container from "./components/container/Container";
import NotFound from "./components/not-found/NotFound";
import Loader from "./components/loader/Loader";

import Login from "./pages/login/Login";
import SignUp from "./pages/signup/SignUp";

import Chats from "./pages/chats/Chats";
import Feed from "./pages/feed/Feed";
import People from "./pages/people/People";
import Profile from "./pages/profile/Profile";
import Articles from "./pages/articles/Articles";
import ArticleDetails from "./pages/article-details/ArticleDetails";
import ArticleEditor from "./pages/article-editor/ArticleEditor";
import Videos from "./pages/videos/Videos";
import VideoDetails from "./pages/video-details/VideoDetails";
import VideoEditor from "./pages/video-editor/VideoEditor";
import Courses from "./pages/courses/Courses";

import GlobalFeed from "./pages/global-feed/GlobalFeed";
import PersonalFeed from "./pages/personal-feed/PersonalFeed";

import SearchResults from "./pages/search-results/SearchResults";

import UserDetails from "./pages/user-details/UserDetails";
import ChatDetails from "./components/chat-details/ChatDetails";


function Layout() {
    return (
        <>
            <Sidebar />
            <Container />
        </>
    )
}

function ArticlesLayout() {
    return <Outlet />;
}

function VideosLayout() {
    return <Outlet />;
}

const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        errorElement: <NotFound />,
        children: [
            {
                path: "search",
                element: <SearchResults />,
            },
            {
                path: "login",
                element: <Login />,
            },
            {
                path: "signup",
                element: <SignUp />,
            },
            {
                path: "chats",
                element: <Chats />,
                children: [
                    {
                        path: ":chatId",
                        element: <ChatDetails />,
                    },
                ]
            },
            {
                path: "people",
                element: <People />,
            },
            {
                path: "people/:username",
                element: <UserDetails />,
            },
            {
                path: "feed",
                element: <Feed />,
                children: [
                    {
                        path: "",
                        element: <GlobalFeed />,
                    },
                    {
                        path: "personal",
                        element: <PersonalFeed />,
                    },
                ]
            },
            {
                path: "articles",
                element: <ArticlesLayout />,
                children: [
                    {
                        path: "",
                        element: <Articles />,
                    },
                    {
                        path: "new",
                        element: <ArticleEditor />,
                    },
                    {
                        path: ":articleId/edit",
                        element: <ArticleEditor />,
                    },
                    {
                        path: ":articleId",
                        element: <ArticleDetails />,
                    },
                ],
            },
            {
                path: "videos",
                element: <VideosLayout />,
                children: [
                    {
                        path: "",
                        element: <Videos />,
                    },
                    {
                        path: "new",
                        element: <VideoEditor />,
                    },
                    {
                        path: ":videoId/edit",
                        element: <VideoEditor />,
                    },
                    {
                        path: ":videoId",
                        element: <VideoDetails />,
                    },
                ],
            },
            {
                path: "courses",
                element: <Courses />,
            },
            {
                path: "profile",
                element: <Profile />,
            },
        ]
    }
])

function App() {
    const { store } = useContext(StoreContext);

    useEffect(() => {
        if (localStorage.getItem('token')) {
            store.checkAuth();
        }
    }, [store]);

    if (store.isLoading) {
        return <Loader />
    }

    return (
        <RouterProvider router={router} />
    )
}

export default observer(App);
