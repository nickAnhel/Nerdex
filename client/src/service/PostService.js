import api from "../http";


export default class PostService {
    static async createPost(data) {
        return api.post("/posts", data);
    }

    static async getPost(postId) {
        return api.get(`/posts/${postId}`);
    }

    static async getPosts(params) {
        return api.get("/posts/list", { params });
    }

    static async getSubscriptionsPosts(params) {
        return api.get("/posts/subscriptions", { params });
    }

    static async likePost(postId) {
        return api.post(`/posts/${postId}/like`);
    }

    static async unlikePost(postId) {
        return api.delete(`/posts/${postId}/like`);
    }

    static async dislikePost(postId) {
        return api.post(`/posts/${postId}/dislike`);
    }

    static async undislikePost(postId) {
        return api.delete(`/posts/${postId}/dislike`);
    }

    static async updatePost(postId, data) {
        return api.put(`/posts/${postId}`, data);
    }

    static async deletePost(postId) {
        return api.delete(`/posts/${postId}`);
    }
}
