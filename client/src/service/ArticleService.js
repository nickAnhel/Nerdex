import api from "../http";


export default class ArticleService {
    static async createArticle(data) {
        return api.post("/articles", data);
    }

    static async getArticle(articleId) {
        return api.get(`/articles/${articleId}`);
    }

    static async getArticleEditor(articleId) {
        return api.get(`/articles/${articleId}/editor`);
    }

    static async getArticles(params) {
        return api.get("/articles/list", { params });
    }

    static async updateArticle(articleId, data) {
        return api.put(`/articles/${articleId}`, data);
    }

    static async deleteArticle(articleId) {
        return api.delete(`/articles/${articleId}`);
    }

    static async likeArticle(articleId) {
        return api.post(`/articles/${articleId}/like`);
    }

    static async unlikeArticle(articleId) {
        return api.delete(`/articles/${articleId}/like`);
    }

    static async dislikeArticle(articleId) {
        return api.post(`/articles/${articleId}/dislike`);
    }

    static async undislikeArticle(articleId) {
        return api.delete(`/articles/${articleId}/dislike`);
    }
}
