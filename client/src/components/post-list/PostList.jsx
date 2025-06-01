import { useState, createRef, useRef, useEffect } from "react";
import { useQuery } from "@siberiacancode/reactuse";
import "./PostList.css"

import PostListItem from "../post-list-item/PostListItem";
import Loader from "../loader/Loader";


const POSTS_IN_PORTION = 5;


function PostList({ fetchPosts, filters, refresh }) {
    const lastItem = createRef();
    const observerLoader = useRef();

    const [posts, setPosts] = useState([]);
    const [offset, setOffset] = useState(0);

    const removePost = (postId) => {
        setPosts((prevPosts) => prevPosts.filter((post) => post.post_id != postId))
    }

    useEffect(() => {
        setOffset(0);
        setPosts([]);
    }, [refresh]);

    const { isLoading, isError, isSuccess, error } = useQuery(
        async () => {
            const params = {
                ...filters,
                offset: offset,
                limit: POSTS_IN_PORTION,
            }
            const res = await fetchPosts(params);
            return res.data;
        },
        {
            keys: [offset, refresh],
            onSuccess: (fetchedPosts) => {
                setPosts((prevPosts) => [...prevPosts, ...fetchedPosts]);
            }

        }
    );

    const actionInSight = (entries) => {
        if (entries[0].isIntersecting && offset < POSTS_IN_PORTION * 10) {
            setOffset((prev) => prev + POSTS_IN_PORTION);
        }
    };

    useEffect(() => {
        if (observerLoader.current) {
            observerLoader.current.disconnect();
        }

        observerLoader.current = new IntersectionObserver(actionInSight);

        if (lastItem.current) {
            observerLoader.current.observe(lastItem.current);
        }
    }, [lastItem]);

    if (isError) {
        console.log(error);
        return;
    }

    return (
        <div className="post-list">
            <div className="posts">
                {
                    posts.map((post, index) => {
                        if (index + 1 == posts.length) {
                            return <PostListItem key={post.post_id} post={post} removePost={removePost} ref={lastItem}/>
                        }
                        return <PostListItem key={post.post_id} post={post} removePost={removePost} />
                    })
                }
                {
                    (!isLoading && posts.length == 0) ? <div className="hint">No posts</div> : ""
                }
            </div>

            {
                isLoading &&
                <div className="loader"><Loader /></div>
            }
        </div>
    )
}

export default PostList;