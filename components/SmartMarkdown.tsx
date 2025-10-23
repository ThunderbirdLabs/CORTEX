import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface SmartMarkdownProps {
  content: string
}

const SmartMarkdown = ({ content }: SmartMarkdownProps) => {
  const components = {
    code({ node, inline, className, children, ...props }: any) {
      return !inline ? (
        <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto my-3">
          <code className="text-sm font-mono" {...props}>
            {String(children).replace(/\n$/, '')}
          </code>
        </pre>
      ) : (
        <code className="bg-purple-50 text-purple-600 px-1.5 py-0.5 rounded text-sm font-mono" {...props}>
          {children}
        </code>
      )
    },
    table: ({ children }: any) => (
      <div className="overflow-x-auto my-4">
        <table className="min-w-full border-collapse border border-gray-700 bg-gray-800 text-white rounded-lg">
          {children}
        </table>
      </div>
    ),
    th: ({ children }: any) => (
      <th className="border border-gray-600 px-4 py-2 bg-gray-700 text-left font-semibold">
        {children}
      </th>
    ),
    td: ({ children }: any) => (
      <td className="border border-gray-600 px-4 py-2">
        {children}
      </td>
    ),
    h1: ({ children }: any) => (
      <h1 className="text-2xl font-bold text-gray-900 mt-4 mb-3 tracking-tight">
        {children}
      </h1>
    ),
    h2: ({ children }: any) => (
      <h2 className="text-xl font-bold text-gray-900 mt-4 mb-2 tracking-tight">
        {children}
      </h2>
    ),
    h3: ({ children }: any) => (
      <h3 className="text-lg font-bold text-gray-900 mt-3 mb-2 border-b border-gray-200 pb-1">
        {children}
      </h3>
    ),
    p: ({ children }: any) => (
      <p className="text-gray-800 leading-relaxed my-2">
        {children}
      </p>
    ),
    strong: ({ children }: any) => (
      <strong className="text-gray-900 font-bold">
        {children}
      </strong>
    ),
    em: ({ children }: any) => (
      <em className="text-gray-700 italic">
        {children}
      </em>
    ),
    ul: ({ children }: any) => (
      <ul className="my-3 list-disc pl-5">
        {children}
      </ul>
    ),
    ol: ({ children }: any) => (
      <ol className="my-3 list-decimal pl-5">
        {children}
      </ol>
    ),
    li: ({ children }: any) => (
      <li className="text-gray-800 my-1.5 leading-relaxed">
        {children}
      </li>
    ),
    blockquote: ({ children }: any) => (
      <blockquote className="border-l-4 border-blue-500 pl-4 italic text-gray-700 my-3">
        {children}
      </blockquote>
    ),
    a: ({ children, href, ...props }: any) => (
      <a 
        href={href} 
        className="text-blue-600 underline font-medium hover:text-blue-700"
        {...props}
      >
        {children}
      </a>
    ),
    hr: () => (
      <hr className="border-gray-300 my-4" />
    )
  }

  return (
    <div className="max-w-none">
      <ReactMarkdown components={components} remarkPlugins={[remarkGfm]}>
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default SmartMarkdown