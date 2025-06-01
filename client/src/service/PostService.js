import api from "../http";


export default class PostService {
    static async createPost(postId, data) {
        return api.post("/posts", data)
    }

    static async getPosts(params) {
        return api.get("/posts/list", { params })
    }

    static async getSubscriptionsPosts(params) {
        return api.get("/posts/subscriptions", { params })
    }

    static async likePost(postId) {
        return api.post(`/posts/like?post_id=${postId}`);
    }

    static async unlikePost(postId) {
        return api.delete(`/posts/like?post_id=${postId}`);
    }

    static async dislikePost(postId) {
        return api.post(`/posts/dislike?post_id=${postId}`);
    }

    static async undislikePost(postId) {
        return api.delete(`/posts/dislike?post_id=${postId}`);
    }

    static async updatePost(postId, data) {
        return api.put(`/posts?post_id=${postId}`, data)
    }

    static async deletePost(postId) {
        return api.delete(`/posts?post_id=${postId}`);
    }
}