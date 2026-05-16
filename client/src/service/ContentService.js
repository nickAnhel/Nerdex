import api from "../http";


export default class ContentService {
    static async getFeed(params) {
        return api.get("/contents/list", { params });
    }

    static async getPublications(params) {
        return api.get("/contents/publications", { params });
    }

    static async getGallery(params) {
        return api.get("/contents/gallery", { params });
    }

    static async getSubscriptionsFeed(params) {
        return api.get("/contents/subscriptions", { params });
    }

    static async getVideoRecommendations(params) {
        return api.get("/contents/videos/recommendations", { params });
    }

    static async getVideoSubscriptions(params) {
        return api.get("/contents/videos/subscriptions", { params });
    }

    static async getHistory(params) {
        return api.get("/contents/history", { params });
    }

    static async getSimilarContent(contentId, params) {
        return api.get(`/recommendations/content/${contentId}/similar`, { params });
    }

    static async setReaction(contentId, reactionType) {
        return api.post(`/contents/${contentId}/reaction`, { reaction_type: reactionType });
    }

    static async removeReaction(contentId, reactionType = null) {
        return api.delete(`/contents/${contentId}/reaction`, {
            data: reactionType ? { reaction_type: reactionType } : null,
        });
    }

    static async startViewSession(contentId, data) {
        return api.post(`/contents/${contentId}/view-session/start`, data);
    }

    static async heartbeatViewSession(contentId, sessionId, data) {
        return api.post(`/contents/${contentId}/view-session/${sessionId}/heartbeat`, data);
    }

    static async finishViewSession(contentId, sessionId, data) {
        return api.post(`/contents/${contentId}/view-session/${sessionId}/finish`, data);
    }

    static async shareToChats(contentId, chatIds, content = "") {
        return api.post("/messages/share-content", {
            content_id: contentId,
            chat_ids: chatIds,
            content,
        });
    }
}
