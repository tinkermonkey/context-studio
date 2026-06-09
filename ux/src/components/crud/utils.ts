export function pluralize(label: string, count: number): string {
  if (count === 1) return label;
  if (label.endsWith("y") && !/[aeiou]y$/i.test(label)) return label.slice(0, -1) + "ies";
  if (/[sxz]$/.test(label) || /[sc]h$/.test(label)) return label + "es";
  return label + "s";
}
