"use client"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-sm leading-relaxed text-gray-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0 whitespace-pre-wrap">{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => <ul className="mb-2 ml-5 list-disc space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="mb-2 ml-5 list-decimal space-y-0.5">{children}</ol>,
          li: ({ children }) => <li className="pl-0.5">{children}</li>,
          h1: ({ children }) => <h1 className="mb-2 mt-1 text-base font-bold text-gray-900">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-2 mt-1 text-sm font-bold text-gray-900">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-1 mt-1 text-sm font-semibold text-gray-900">{children}</h3>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-600 underline">{children}</a>
          ),
          code: ({ className, children }) => {
            const isBlock = (className || "").includes("language-")
            if (isBlock) {
              return (
                <code className="block overflow-auto rounded-lg bg-gray-900 p-3 font-mono text-xs text-gray-100 whitespace-pre">{children}</code>
              )
            }
            return <code className="rounded bg-gray-100 px-1 py-0.5 font-mono text-[0.85em] text-gray-800">{children}</code>
          },
          pre: ({ children }) => <pre className="mb-2 overflow-auto">{children}</pre>,
          table: ({ children }) => (
            <div className="mb-2 overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
          th: ({ children }) => <th className="border border-gray-200 px-2 py-1 text-left font-semibold text-gray-700">{children}</th>,
          td: ({ children }) => <td className="border border-gray-200 px-2 py-1 text-gray-700">{children}</td>,
          blockquote: ({ children }) => <blockquote className="mb-2 border-l-2 border-gray-300 pl-3 text-gray-600">{children}</blockquote>,
          hr: () => <hr className="my-3 border-gray-200" />,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
