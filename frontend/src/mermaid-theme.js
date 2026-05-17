/** Elegant mindmap theme — warm paper palette, serif labels */
export const MERMAID_CONFIG = {
  startOnLoad: false,
  securityLevel: 'loose',
  theme: 'base',
  themeVariables: {
    fontFamily: '"Noto Serif SC", "Songti SC", "STSong", serif',
    fontSize: '15px',
    primaryColor: '#F3EDE4',
    primaryTextColor: '#3D3832',
    primaryBorderColor: '#C9B99A',
    secondaryColor: '#E8E0D4',
    secondaryTextColor: '#4A433C',
    secondaryBorderColor: '#B8A990',
    tertiaryColor: '#FAF7F2',
    tertiaryTextColor: '#5C5348',
    tertiaryBorderColor: '#D4C8B8',
    lineColor: '#A89888',
    textColor: '#3D3832',
    mainBkg: '#F3EDE4',
    nodeBorder: '#C9B99A',
    clusterBkg: '#FAF7F2',
    clusterBorder: '#D4C8B8',
    titleColor: '#2C2825',
    edgeLabelBackground: '#FAF7F2',
  },
  mindmap: {
    padding: 24,
    useMaxWidth: true,
  },
}

/** Post-render: soften mindmap SVG fills & typography */
export function polishMindmapSvg(svgHtml) {
  if (!svgHtml || typeof svgHtml !== 'string') return svgHtml
  return svgHtml
    .replace(/fill="#FFD700"/gi, 'fill="#E8DFD0"')
    .replace(/fill="#FFFF00"/gi, 'fill="#F0E8DC"')
    .replace(/fill="#FFEE58"/gi, 'fill="#EDE4D6"')
    .replace(/stroke="#333"/gi, 'stroke="#C9B99A"')
}
