import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import "./PostDetails.css";

import Loader from "../../components/loader/Loader";
import CommentSection from "../../components/comment-section/CommentSection";
import Modal from "../../components/modal/Modal";
import PostListItem from "../../components/post-list-item/PostListItem";
import PostService from "../../service/PostService";


function PostDetails() {
    const [searchParams, setSearchParams] = useSearchParams();
    const postId = searchParams.get("p");
    const mediaParam = searchParams.get("media");
    const initialGalleryIndex = mediaParam === null ? null : Number.parseInt(mediaParam, 10);

    const [isLoading, setIsLoading] = useState(true);
    const [post, setPost] = useState(null);
    const [isUnavailable, setIsUnavailable] = useState(false);

    const handleCommentsCountChange = (delta) => {
        setPost((prevPost) => {
            if (!prevPost) {
                return prevPost;
            }

            return {
                ...prevPost,
                comments_count: Math.max(0, prevPost.comments_count + delta),
            };
        });
    };

    const closePostDetails = () => {
        const nextSearchParams = new URLSearchParams(searchParams);
        nextSearchParams.delete("p");
        nextSearchParams.delete("media");
        setSearchParams(nextSearchParams);
    };

    const closeGallery = () => {
        const nextSearchParams = new URLSearchParams(searchParams);
        nextSearchParams.delete("media");
        setSearchParams(nextSearchParams);
    };

    const updateGalleryIndex = (index) => {
        const nextSearchParams = new URLSearchParams(searchParams);
        nextSearchParams.set("media", String(index));
        setSearchParams(nextSearchParams);
    };

    useEffect(() => {
        if (!postId) {
            setIsLoading(false);
            setIsUnavailable(false);
            setPost(null);
            return;
        }

        const fetchPost = async () => {
            setIsLoading(true);
            setIsUnavailable(false);

            try {
                const res = await PostService.getPost(postId);
                setPost(res.data);
            } catch (e) {
                setIsUnavailable(true);
                setPost(null);
            } finally {
                setIsLoading(false);
            }
        };

        fetchPost();
    }, [postId]);

    if (!postId) {
        return null;
    }

    if (isLoading) {
        return (
            <Modal active={true} setActive={closePostDetails}>
                <div id="post-details">
                    <div className="loader-wrapper">
                        <Loader />
                    </div>
                </div>
            </Modal>
        );
    }

    if (isUnavailable || !post) {
        return (
            <Modal active={true} setActive={closePostDetails}>
                <div id="post-details">
                    <div className="post-state-card">
                        <h2>Post unavailable</h2>
                        <p>This post is private, still a draft, deleted, or does not exist.</p>
                    </div>
                </div>
            </Modal>
        );
    }

    return (
            <Modal active={true} setActive={closePostDetails}>
                <div id="post-details">
                    <PostListItem
                        post={post}
                        showDetailLink={false}
                        onDelete={closePostDetails}
                        initialGalleryIndex={Number.isNaN(initialGalleryIndex) ? null : initialGalleryIndex}
                        onGalleryClose={closeGallery}
                        onGalleryIndexChange={updateGalleryIndex}
                    />
                    <div className="post-details-comments">
                        <CommentSection
                            contentId={post.post_id}
                            isEnabled={post.status === "published"}
                            onCommentsCountChange={handleCommentsCountChange}
                        />
                    </div>
                </div>
            </Modal>
        );
}

export default PostDetails;
