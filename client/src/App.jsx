import { useEffect, useContext } from "react";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
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
    }, []);

    if (store.isLoading) {
        return <Loader />
    }

    return (
        <RouterProvider router={router} />
    )
}

export default observer(App);
