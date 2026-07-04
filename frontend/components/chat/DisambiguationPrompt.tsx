"use client"
interface DisambiguationPromptProps {
  question: string
  options: string[]
  onSelect: (option: string) => void
  resolved?: boolean
  selectedOption?: string
}

export function DisambiguationPrompt({ question, options, onSelect, resolved = false, selectedOption }: DisambiguationPromptProps) {
  return (
    <div className="my-2 rounded-xl border border-indigo-100 bg-indigo-50 p-3">
      <p className="mb-2 text-sm text-gray-700">{question}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const isSelected = option === selectedOption
          const isOther = resolved && selectedOption && option !== selectedOption
          return (
            <button key={option} onClick={() => !resolved && onSelect(option)} disabled={resolved}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-all disabled:cursor-default
                ${isSelected ? "border-indigo-600 bg-indigo-600 text-white" : isOther ? "border-gray-200 bg-white text-gray-400 opacity-50" : "border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-100"}`}>
              {option}
            </button>
          )
        })}
      </div>
    </div>
  )
}
