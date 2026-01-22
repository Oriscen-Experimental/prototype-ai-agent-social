export function OptionGroup(props: {
  title: string
  options: Array<{ value: string; label: string }>
  value: string | null
  onChange: (next: string) => void
}) {
  return (
    <div className="optionGroup">
      <div className="optionTitle">{props.title}</div>
      <div className="optionRow">
        {props.options.map((o) => (
          <button
            key={o.value}
            type="button"
            className={props.value === o.value ? 'chip chipActive' : 'chip'}
            onClick={() => props.onChange(o.value)}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

