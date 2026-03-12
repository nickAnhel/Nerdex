import api from "../http";


export default class CommentService {
    static async getContentComments(contentId, params) {
        return api.get(`/contents/${contentId}/comments`, { params });
    }

    static async createContentComment(contentId, data) {
        return api.post(`/contents/${contentId}/comments`, data);
    }

    static async getReplies(commentId, params) {
        return api.get(`/comments/${commentId}/replies`, { params });
    }

    static async createReply(commentId, data) {
        return api.post(`/comments/${commentId}/replies`, data);
    }

    static async updateComment(commentId, data) {
        return api.patch(`/comments/${commentId}`, data);
    }

    static async deleteComment(commentId) {
        return api.delete(`/comments/${commentId}`);
    }

    static async likeComment(commentId) {
        return api.post(`/comments/${commentId}/like`);
    }

    static async unlikeComment(commentId) {
        return api.delete(`/comments/${commentId}/like`);
    }

    static async dislikeComment(commentId) {
        return api.post(`/comments/${commentId}/dislike`);
    }

    static async undislikeComment(commentId) {
        return api.delete(`/comments/${commentId}/dislike`);
    }
}
