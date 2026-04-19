import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

import "./ArticleRenderer.css";

import { buildArticleAssetLookup, buildMermaidPreviewUrl, parseArticleMarkdown, slugifyHeading } from "../../utils/articleMarkdown";


function MarkdownBlock({ content }) {
    if (!content?.trim()) {
        return null;
    }

    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                h2({ children, ...props }) {
                    const text = Array.isArray(children) ? children.join("") : String(children || "");
                    return <h2 id={slugifyHeading(text)} {...props}>{children}</h2>;
                },
                h3({ children, ...props }) {
                    const text = Array.isArray(children) ? children.join("") : String(children || "");
                    return <h3 id={slugifyHeading(text)} {...props}>{children}</h3>;
                },
                code({ inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    return !inline && match ? (
                        <SyntaxHighlighter
                            style={oneDark}
                            language={match[1]}
                            PreTag="div"
                            customStyle={{ margin: 0, borderRadius: "1rem" }}
                            {...props}
                        >
                            {String(children).replace(/\n$/, "")}
                        </SyntaxHighlighter>
                    ) : (
                        <code className={className} {...props}>
                            {children}
                        </code>
                    );
                },
            }}
        >
            {content}
        </ReactMarkdown>
    );
}

function ArticleRenderer({
    bodyMarkdown,
    article = null,
    extraAssets = [],
    renderMode = "default",
    onEditMermaid = null,
}) {
    const blocks = parseArticleMarkdown(bodyMarkdown || "");
    const assetLookup = buildArticleAssetLookup(article, extraAssets);
    let mermaidIndex = -1;

    return (
        <div className="article-renderer">
            {
                blocks.map((block, index) => {
                    if (block.type === "markdown") {
                        return <MarkdownBlock key={`markdown-${index}`} content={block.content} />;
                    }

                    if (block.type === "spoiler") {
                        return (
                            <details className="article-spoiler" key={`spoiler-${index}`}>
                                <summary>{block.title || "Spoiler"}</summary>
                                <ArticleRenderer
                                    bodyMarkdown={block.bodyMarkdown}
                                    article={article}
                                    extraAssets={extraAssets}
                                    renderMode={renderMode}
                                    onEditMermaid={onEditMermaid}
                                />
                            </details>
                        );
                    }

                    if (block.type === "image") {
                        const asset = assetLookup[block.attrs["asset-id"]];
                        if (!asset) {
                            return (
                                <div
                                    className={renderMode === "editor" ? "article-pending-asset" : "article-missing-asset"}
                                    key={`image-${index}`}
                                >
                                    {renderMode === "editor" ? "Loading image preview..." : `Missing image asset: ${block.attrs["asset-id"]}`}
                                </div>
                            );
                        }

                        return (
                            <figure className={`article-figure ${block.attrs.size || "wide"}`} key={`image-${index}`}>
                                <img
                                    src={asset.original_url || asset.preview_url}
                                    alt={block.attrs.caption || asset.original_filename || "Article image"}
                                />
                                {block.attrs.caption && <figcaption>{block.attrs.caption}</figcaption>}
                            </figure>
                        );
                    }

                    if (block.type === "video") {
                        const asset = assetLookup[block.attrs["asset-id"]];
                        if (!asset) {
                            return (
                                <div
                                    className={renderMode === "editor" ? "article-pending-asset" : "article-missing-asset"}
                                    key={`video-${index}`}
                                >
                                    {renderMode === "editor" ? "Loading video preview..." : `Missing video asset: ${block.attrs["asset-id"]}`}
                                </div>
                            );
                        }

                        return (
                            <figure className={`article-video-block ${block.attrs.size || "wide"}`} key={`video-${index}`}>
                                <video
                                    controls
                                    preload="metadata"
                                    poster={asset.poster_url || undefined}
                                    src={asset.stream_url || asset.original_url}
                                />
                                {block.attrs.caption && <figcaption>{block.attrs.caption}</figcaption>}
                            </figure>
                        );
                    }

                    if (block.type === "youtube") {
                        const embedUrl = `https://www.youtube.com/embed/${block.attrs.id}`;
                        return (
                            <figure className="article-youtube-block" key={`youtube-${index}`}>
                                <div className="article-youtube-frame">
                                    <iframe
                                        src={embedUrl}
                                        title={block.attrs.title || "YouTube video"}
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                        allowFullScreen
                                    />
                                </div>
                                {block.attrs.title && <figcaption>{block.attrs.title}</figcaption>}
                            </figure>
                        );
                    }

                    if (block.type === "mermaid") {
                        mermaidIndex += 1;
                        const previewUrl = buildMermaidPreviewUrl(block.code);
                        return (
                            <figure className="article-mermaid-block" key={`mermaid-${index}`}>
                                <div className="article-mermaid-header">
                                    <div className="article-mermaid-label">Mermaid diagram</div>
                                    {
                                        renderMode === "editor" && onEditMermaid &&
                                        <button
                                            type="button"
                                            className="article-mermaid-edit-button"
                                            onClick={() => onEditMermaid({ code: block.code, index: mermaidIndex })}
                                        >
                                            Edit
                                        </button>
                                    }
                                </div>
                                {
                                    previewUrl
                                        ? (
                                            <img
                                                className="article-mermaid-image"
                                                src={previewUrl}
                                                alt="Mermaid diagram"
                                                onError={(event) => {
                                                    event.currentTarget.style.display = "none";
                                                    event.currentTarget.nextElementSibling?.classList.add("visible");
                                                }}
                                            />
                                        )
                                        : null
                                }
                                <pre className={`article-mermaid-code ${previewUrl ? "" : "visible"}`}>{block.code}</pre>
                            </figure>
                        );
                    }

                    return null;
                })
            }
        </div>
    );
}

export default ArticleRenderer;
