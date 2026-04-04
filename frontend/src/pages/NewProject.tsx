import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Settings, Sparkles, CheckCircle, Loader2, RefreshCcw, ArrowLeft, Trash2, Pencil, Save, X, ChevronDown } from 'lucide-react'
import { createProject, getProjects, getLLMConfigFromStorage, evaluateEntropy, listFrameworkTemplates, initializeProjectWithTemplate, getConfigValues, createAndInitializeProject, getEmbedConfigFromStorage, getUserIdFromStorage, acquireKnowledge, summarizeKnowledge, parseKnowledgeFiles, type KnowledgeItem, type KnowledgeMode } from '@/api/client'
import Sidebar, { SidebarProject } from '@/components/Sidebar'

export default function NewProject() {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [initialDesc, setInitialDesc] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingText, setLoadingText] = useState<string>('')
  
  const [projects, setProjects] = useState<SidebarProject[]>([])
  const [entropy, setEntropy] = useState<number | null>(null)
  const [semanticScore, setSemanticScore] = useState<number | null>(null)
  const [lengthScore, setLengthScore] = useState<number | null>(null)
  const [summary, setSummary] = useState<{ core_goal?: string; core_users?: string[]; core_functions?: string[]; constraints?: string[]; acceptance?: string[] } | null>(null)
  const [phase, setPhase] = useState<'create' | 'review'>('create')
  const [reviewDraft, setReviewDraft] = useState('')
  const [reviewSaving, setReviewSaving] = useState(false)
  const [projectInfo, setProjectInfo] = useState('')
  const [retrievalOpen, setRetrievalOpen] = useState(false)
  const [retrievalCandidates, setRetrievalCandidates] = useState<KnowledgeItem[]>([])
  const [retrievalThresholdUsed, setRetrievalThresholdUsed] = useState<number | null>(null)
  const [retrievalLoading, setRetrievalLoading] = useState(false)
  const [retrievalProgress, setRetrievalProgress] = useState(0)
  const [retrievalStageText, setRetrievalStageText] = useState('')
  const [retrievalError, setRetrievalError] = useState<string | null>(null)
  const [retrievalWebKnowledgeDict, setRetrievalWebKnowledgeDict] = useState<Record<string, { query?: string; title?: string; key_insights?: string; content?: string; tags?: string[] }>>({})
  const [collapsedSources, setCollapsedSources] = useState<Record<string, boolean>>({})
  const [editingCardIndexes, setEditingCardIndexes] = useState<Record<number, boolean>>({})
  const [editingDrafts, setEditingDrafts] = useState<Record<number, KnowledgeItem>>({})
  const [generatingFramework, setGeneratingFramework] = useState(false)
  const [knowledgeMode, setKnowledgeMode] = useState<KnowledgeMode | 'none'>('basic')
  const [uploadedFiles, setUploadedFiles] = useState<FileList | null>(null)
  const [saveKnowledgeToLibrary, setSaveKnowledgeToLibrary] = useState(false)
  const [templates, setTemplates] = useState<{ template_id: number; template_name: string }[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null)
  const [entropyThresholdUsed, setEntropyThresholdUsed] = useState<number | null>(null)

  const navigate = useNavigate()

  useEffect(() => {
    (async () => {
      try {
        const cfg = await getConfigValues()
        setEntropyThresholdUsed((cfg.entropy_threshold ?? null) as number | null)
        setRetrievalThresholdUsed((cfg.retrieval_cosine_threshold ?? null) as number | null)
      } catch (e) {
        console.error('加载系统配置失败', e)
        setError('系统配置加载失败')
      }
      const data = await getProjects()
      setProjects(data.projects)
      const userRaw = localStorage.getItem('user')
      const user = userRaw ? JSON.parse(userRaw) as { user_id?: number } : null
      const userId = user?.user_id as number | undefined
      const ts = await listFrameworkTemplates(userId) as { templates: { template_id: number; template_name: string }[] }
      setTemplates(ts.templates || [])
      const savedName = localStorage.getItem('new_project_name')
      const savedDesc = localStorage.getItem('new_project_desc')
      const savedInitialDesc = localStorage.getItem('new_project_initial_desc')
      const savedProjectInfo = localStorage.getItem('new_project_projectInfo')
      const savedSummary = localStorage.getItem('new_project_summary')
      if (savedName) setName(savedName)
      if (savedDesc) setDesc(savedDesc)
      if (savedInitialDesc) setInitialDesc(savedInitialDesc)
      if (savedProjectInfo) setProjectInfo(savedProjectInfo)
      if (savedSummary) {
        setSummary(JSON.parse(savedSummary))
      }
    })()
  }, [])

  const defaultTemplate = '核心目标：\n- \n\n核心用户：\n- \n\n核心功能：\n- \n\n关键约束（时间/预算/技术/合规）：\n- \n\n验收标准（可度量）：\n- '

  const sourceLabel = (source: string) => {
    if (source === 'DB_RETRIEVAL') return '数据库检索'
    if (source === 'WEB_SEARCH') return '网络搜索'
    if (source === 'LLM_GEN') return '模型生成'
    if (source === 'FILE_UPLOAD') return '上传文件'
    return source
  }

  const groupedRetrievalCandidates = useMemo(() => {
    const groups: { source: string; items: { item: KnowledgeItem; index: number }[] }[] = []
    const indexBySource: Record<string, number> = {}
    retrievalCandidates.forEach((item, index) => {
      const source = item.source || 'UNKNOWN'
      const pos = indexBySource[source]
      if (typeof pos === 'number') {
        groups[pos].items.push({ item, index })
      } else {
        indexBySource[source] = groups.length
        groups.push({ source, items: [{ item, index }] })
      }
    })
    return groups
  }, [retrievalCandidates])

  const getSourceOverview = (source: string, items: { item: KnowledgeItem; index: number }[]) => {
    if (source === 'WEB_SEARCH') {
      const querySet = new Set<string>()
      Object.values(retrievalWebKnowledgeDict).forEach(v => {
        const q = String(v?.query || '').trim()
        if (q) querySet.add(q)
      })
      const webCountFromDict = Object.keys(retrievalWebKnowledgeDict).length
      const webCountFromItems = items.filter(x => (x.item.reference || '').startsWith('http')).length
      const webCount = webCountFromDict || webCountFromItems
      return `共${items.length}张卡片 · 检索词${querySet.size}个 · 网页来源${webCount}个`
    }
    return `共${items.length}张卡片`
  }

  const toggleSourceCollapse = (source: string) => {
    setCollapsedSources(prev => ({ ...prev, [source]: !(prev[source] ?? false) }))
  }

  const startEditCard = (index: number) => {
    const current = retrievalCandidates[index]
    if (!current) return
    setEditingDrafts(prev => ({
      ...prev,
      [index]: {
        ...current,
        tags: Array.isArray(current.tags) ? [...current.tags] : [],
      },
    }))
    setEditingCardIndexes(prev => ({ ...prev, [index]: true }))
  }

  const updateEditDraft = (index: number, patch: Partial<KnowledgeItem>) => {
    setEditingDrafts(prev => {
      const base = prev[index] || retrievalCandidates[index]
      if (!base) return prev
      return { ...prev, [index]: { ...base, ...patch } }
    })
  }

  const saveEditCard = (index: number) => {
    const draft = editingDrafts[index]
    if (!draft) return
    setRetrievalCandidates(prev => prev.map((item, idx) => (idx === index ? draft : item)))
    setEditingCardIndexes(prev => {
      const next = { ...prev }
      delete next[index]
      return next
    })
    setEditingDrafts(prev => {
      const next = { ...prev }
      delete next[index]
      return next
    })
  }

  const cancelEditCard = (index: number) => {
    setEditingCardIndexes(prev => {
      const next = { ...prev }
      delete next[index]
      return next
    })
    setEditingDrafts(prev => {
      const next = { ...prev }
      delete next[index]
      return next
    })
  }

  const deleteCard = (index: number) => {
    setRetrievalCandidates(prev => prev.filter((_, idx) => idx !== index))
    setEditingCardIndexes(prev => {
      const next: Record<number, boolean> = {}
      Object.entries(prev).forEach(([k, v]) => {
        if (!v) return
        const n = Number(k)
        if (n < index) next[n] = true
        if (n > index) next[n - 1] = true
      })
      return next
    })
    setEditingDrafts(prev => {
      const next: Record<number, KnowledgeItem> = {}
      Object.entries(prev).forEach(([k, v]) => {
        const n = Number(k)
        if (n < index) next[n] = v
        if (n > index) next[n - 1] = v
      })
      return next
    })
  }

  const fillTemplate = () => {
    setDesc(d => d && d.trim().length > 0 ? d : defaultTemplate)
  }

  const runQualityCheck = async () => {
    if (!name || !desc) return
    setLoading(true)
    setLoadingText('正在生成访谈信息评估...')
    setError(null)
    try {
      if (!initialDesc) setInitialDesc(desc)
      const cfg = getLLMConfigFromStorage()
      if (!cfg) throw new Error('LLM未配置，请在设置中填写')
      const res1 = await evaluateEntropy(cfg, desc)
      const s1 = res1.summary || null
      const formatted = summaryToText(s1)
      const res2 = await evaluateEntropy(cfg, formatted)
      setEntropy(res2.entropy as number)
      setSemanticScore(res2.semantic_score as number)
      setLengthScore(res2.length_score as number)
      setEntropyThresholdUsed((res2.threshold ?? null) as number | null)
      const revisedSummary = res2.summary
      const reviewedText = summaryToText(revisedSummary)
      setSummary(revisedSummary)
      setProjectInfo(reviewedText)
      setReviewDraft(reviewedText)
      setPhase('review')
    } catch (e) {
      const msg = e instanceof Error ? e.message : '计算失败，请检查LLM配置'
      setError(msg)
    }
    setLoading(false)
    setLoadingText('')
  }

  const saveReviewEdit = async () => {
    const content = reviewDraft.trim()
    if (!content) {
      setError('结构化需求内容不能为空')
      return
    }
    const cfg = getLLMConfigFromStorage()
    if (!cfg) {
      setError('LLM未配置，请在设置中填写')
      return
    }
    setReviewSaving(true)
    setError(null)
    try {
      const qc = await evaluateEntropy(cfg, content)
      setEntropy(qc.entropy as number)
      setSemanticScore(qc.semantic_score as number)
      setLengthScore(qc.length_score as number)
      setEntropyThresholdUsed((qc.threshold ?? null) as number | null)
      setSummary((qc.summary || null) as typeof summary)
      setProjectInfo(content)
    } finally {
      setReviewSaving(false)
    }
  }

  const summaryToText = (s: typeof summary) => {
    if (!s) return desc
    const goal = s.core_goal || ''
    const users = (s.core_users || []).map(x => `- ${x}`).join('\n')
    const funcs = (s.core_functions || []).map(x => `- ${x}`).join('\n')
    const cons = (s.constraints || []).map(x => `- ${x}`).join('\n')
    const acc = (s.acceptance || []).map(x => `- ${x}`).join('\n')
    return `核心目标：\n${goal}\n\n核心用户：\n${users}\n\n核心功能：\n${funcs}\n\n关键约束：\n${cons}\n\n验收标准：\n${acc}`
  }

  const executeCreate = async () => {
    if (retrievalOpen || generatingFramework) return
    const finalDesc = (projectInfo || summaryToText(summary) || desc).trim()
    const cfg = getLLMConfigFromStorage()
    if (!cfg) { setError('LLM未配置，请在设置中填写'); return }
    if (selectedTemplateId) {
      setLoading(true)
      setLoadingText('正在创建项目...')
      setError(null)
      const res = await createProject(name, finalDesc)
      const newId = (res && (res.project?.project_id ?? res.project_id ?? res.id)) as number | undefined
      if (newId) {
        try {
          await initializeProjectWithTemplate(newId, selectedTemplateId)
          setLoading(false)
          setLoadingText('')
          navigate('/')
          return
        } catch (e) {
          const msg = e instanceof Error ? e.message : '使用模板初始化失败'
          setError(msg)
        }
      }
      setLoading(false)
      setLoadingText('')
      return
    }
    setLoading(false)
    setLoadingText('')
    await openRetrieval()
  }

  const confirmAndCreate = async () => {
    if (retrievalOpen || generatingFramework) return
    await executeCreate()
  }

  const handleCreateClick = async () => {
    if (selectedTemplateId) {
      if (!name || !desc) return
      setLoading(true)
      setLoadingText('正在创建项目...')
      setError(null)
      const res = await createProject(name, desc)
      const newId = (res && (res.project?.project_id ?? res.project_id ?? res.id)) as number | undefined
      if (newId) {
        try {
          await initializeProjectWithTemplate(newId, selectedTemplateId)
          setLoading(false)
          setLoadingText('')
          navigate('/')
          return
        } catch (e) {
          const msg = e instanceof Error ? e.message : '使用模板初始化失败'
          setError(msg)
        }
      }
      setLoading(false)
      setLoadingText('')
    } else {
      await runQualityCheck()
    }
  }

  const openRetrieval = async () => {
    setRetrievalOpen(true)
    setRetrievalLoading(true)
    setRetrievalProgress(5)
    setRetrievalStageText('正在准备知识获取...')
    setRetrievalError(null)
    setRetrievalCandidates([])
    setRetrievalWebKnowledgeDict({})
    setEditingCardIndexes({})
    setEditingDrafts({})
    const llm = getLLMConfigFromStorage()
    if (!llm) {
      setRetrievalError('LLM未配置，请在设置中填写')
      setRetrievalProgress(0)
      setRetrievalStageText('')
      setRetrievalLoading(false)
      return
    }
    const embed = getEmbedConfigFromStorage()
    const user_id = getUserIdFromStorage()
    const qtext = projectInfo || summaryToText(summary)
    try {
      const collected: KnowledgeItem[] = []
      if (knowledgeMode !== 'none') {
        setRetrievalProgress(20)
        setRetrievalStageText('正在获取领域知识...')
        if (!embed) {
          setRetrievalError('Embedding 未配置，请在设置中填写')
          setRetrievalProgress(0)
          setRetrievalStageText('')
          setRetrievalLoading(false)
          return
        }
        const res = await acquireKnowledge({
          project_name: name,
          initial_requirements: qtext,
          mode: knowledgeMode as KnowledgeMode,
          use_domain_knowledge: true,
          api_url: llm.api_url,
          api_key: llm.api_key,
          model_name: llm.model_name,
          embedding_api_url: embed.api_url,
          embedding_api_key: embed.api_key,
          embedding_model_name: embed.model_name,
          threshold: retrievalThresholdUsed ?? undefined,
          user_id: user_id,
        })
        const cands: KnowledgeItem[] = (res.knowledge_items || []) as KnowledgeItem[]
        const webDict = (res.web_knowledge_dict && typeof res.web_knowledge_dict === 'object')
          ? (res.web_knowledge_dict as Record<string, { query?: string; title?: string; key_insights?: string; content?: string; tags?: string[] }>)
          : {}
        setRetrievalWebKnowledgeDict(webDict)
        collected.push(...cands)
        setRetrievalProgress(70)
        setRetrievalStageText('领域知识获取完成，正在处理上传文件...')
      }
      if (uploadedFiles && uploadedFiles.length > 0) {
        setRetrievalProgress(80)
        setRetrievalStageText('正在解析上传文件...')
        const fd = new FormData()
        Array.from(uploadedFiles).forEach(f => fd.append('files', f))
        const parsed = await parseKnowledgeFiles(fd)
        const fileItems: KnowledgeItem[] = (parsed.knowledge_items || []) as KnowledgeItem[]
        collected.push(...fileItems)
      }
      setRetrievalProgress(95)
      setRetrievalStageText('正在整理知识卡片...')
      setRetrievalCandidates(collected)
      setRetrievalProgress(100)
      setRetrievalStageText('知识获取完成')
    } catch (e) {
      const msg = e instanceof Error ? e.message : '获取知识失败'
      setRetrievalError(msg)
      setRetrievalProgress(0)
      setRetrievalStageText('')
    }
    setRetrievalLoading(false)
  }

  const recomputeRetrieval = async () => {
    await openRetrieval()
  }

  const finalizeCreation = async (fused_text: string) => {
    const cfg = getLLMConfigFromStorage()
    if (!cfg) { setRetrievalError('LLM未配置，请在设置中填写'); return }
    const finalDesc = (projectInfo || summaryToText(summary) || desc).trim()
    try {
      const resp = await createAndInitializeProject(name, finalDesc, cfg, fused_text)
      const newId = (resp && (resp.project?.project_id ?? resp.project_id ?? resp.id)) as number | undefined
      if (newId) localStorage.setItem('selectedProjectId', String(newId))
      setRetrievalOpen(false)
      navigate('/')
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成失败'
      setRetrievalError(msg)
    }
  }

  const generateWithFused = async () => {
    setGeneratingFramework(true)
    setRetrievalError(null)
    try {
      const cfg = getLLMConfigFromStorage()
      if (!cfg) {
        setRetrievalError('LLM未配置，请在设置中填写')
        setGeneratingFramework(false)
        return
      }
      const finalDesc = (projectInfo || summaryToText(summary) || desc).trim()
      const userId = getUserIdFromStorage()
      const embed = getEmbedConfigFromStorage()
      const fr = await summarizeKnowledge({
        project_name: name,
        initial_requirements: finalDesc,
        knowledge_items: retrievalCandidates,
        api_url: cfg.api_url,
        api_key: cfg.api_key,
        model_name: cfg.model_name,
        embedding_api_url: embed?.api_url,
        embedding_api_key: embed?.api_key,
        embedding_model_name: embed?.model_name,
        user_id: userId,
        save_to_library: saveKnowledgeToLibrary,
      })
      const fused_text = String(fr.fused_text || '')
      await finalizeCreation(fused_text)
    } catch (e) {
      const msg = e instanceof Error ? e.message : '生成失败'
      setRetrievalError(msg)
    }
    setGeneratingFramework(false)
  }

  // Persist creation states
  useEffect(() => { localStorage.setItem('new_project_name', name) }, [name])
  useEffect(() => { localStorage.setItem('new_project_desc', desc) }, [desc])
  useEffect(() => { localStorage.setItem('new_project_initial_desc', initialDesc) }, [initialDesc])
  useEffect(() => { localStorage.setItem('new_project_projectInfo', projectInfo) }, [projectInfo])
  useEffect(() => { localStorage.setItem('new_project_summary', JSON.stringify(summary || {})) }, [summary])
  useEffect(() => {
    setCollapsedSources(prev => {
      const next = { ...prev }
      for (const g of groupedRetrievalCandidates) {
        if (typeof next[g.source] !== 'boolean') {
          next[g.source] = false
        }
      }
      return next
    })
  }, [groupedRetrievalCandidates])

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      {loading && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in">
          <div className="relative bg-card rounded-xl shadow-xl border border-border w-[360px] p-6 text-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary mx-auto mb-4"></div>
            <div className="text-sm text-muted-foreground font-medium">{loadingText || '处理中...'}</div>
          </div>
        </div>
      )}

      <Sidebar
        projects={projects}
        selectedProject={null}
        onProjectSelect={(p) => {
          localStorage.setItem('selectedProjectId', String(p.project_id));
          navigate('/');
        }}
        onNewProject={() => navigate('/projects/new')}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden bg-background/50">
        {/* Header */}
        <div className="h-16 border-b border-border bg-card/50 backdrop-blur-sm flex items-center px-6 justify-between flex-shrink-0 z-10">
          <div className="flex items-center space-x-4">
            <button onClick={() => navigate('/')} className="p-2 rounded-full hover:bg-muted text-muted-foreground transition-colors">
              <ArrowLeft className="h-5 w-5" />
            </button>
            <h1 className="text-lg font-semibold">创建新项目</h1>
          </div>
          <div className="flex items-center space-x-2">
            <div className={`h-2 w-2 rounded-full ${phase === 'create' ? 'bg-primary' : 'bg-muted-foreground'}`} />
            <div className={`h-1 w-8 rounded-full ${phase === 'review' ? 'bg-primary' : 'bg-muted'}`} />
            <div className={`h-2 w-2 rounded-full ${phase === 'review' ? 'bg-primary' : 'bg-muted-foreground'}`} />
          </div>
        </div>

        <div className="flex-1 p-6 overflow-hidden flex justify-center">
          {phase === 'create' ? (
            <div className="w-full max-w-4xl animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="bg-card rounded-xl border border-border shadow-sm h-full max-h-[calc(100vh-8rem)] flex flex-col overflow-hidden">
                <div className="p-6 border-b border-border flex items-center justify-between bg-muted/10">
                  <div className="flex items-center space-x-3">
                    <div className="bg-primary/10 p-2 rounded-lg">
                      <Settings className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <h2 className="font-semibold text-foreground">项目基础信息</h2>
                      <p className="text-xs text-muted-foreground">填写项目名称和描述，或使用模板快速开始</p>
                    </div>
                  </div>
                </div>
                
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  {error && (
                    <div className="p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive text-sm flex items-start">
                      <span className="mr-2">⚠️</span> {error}
                    </div>
                  )}
                  
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
                    <div className="lg:col-span-2 space-y-4">
                      <div className="space-y-2">
                        <label className="block text-sm font-medium text-foreground">项目名称</label>
                        <input 
                          value={name} 
                          onChange={e => setName(e.target.value)} 
                          placeholder="给项目起个名字..." 
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="block text-sm font-medium text-foreground">使用模板（可选）</label>
                        <select 
                          value={selectedTemplateId ?? ''} 
                          onChange={e => setSelectedTemplateId(e.target.value ? Number(e.target.value) : null)} 
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        >
                          <option value="">不使用模板</option>
                          {templates.map(t => (<option key={t.template_id} value={t.template_id}>{t.template_name}</option>))}
                        </select>
                        {selectedTemplateId && (
                          <div className="text-xs text-muted-foreground bg-muted/50 p-2 rounded border border-border">
                            选择模板后将直接复用该模板生成访谈框架。
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="rounded-lg border border-border bg-muted/10 p-4 space-y-3">
                      <div className="space-y-1">
                        <label className="block text-sm font-medium text-foreground">知识获取模式</label>
                        <div className="text-xs text-muted-foreground">建议优先选择，影响后续知识融合范围。</div>
                      </div>
                      <select
                        value={knowledgeMode}
                        onChange={e => setKnowledgeMode(e.target.value as KnowledgeMode | 'none')}
                        disabled={!!selectedTemplateId}
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      >
                        <option value="basic">基础模式 Basic（仅检索）</option>
                        <option value="pro">专家模式 Pro（检索+生成）</option>
                        <option value="max">深度模式 Max（检索+联网+生成）</option>
                        <option value="none">不使用领域经验</option>
                      </select>
                      <div className="text-xs text-muted-foreground">
                        当前模式：{knowledgeMode === 'none' ? '不使用领域经验' : knowledgeMode.toUpperCase()}
                      </div>
                      <div className="space-y-2">
                        <label className="block text-xs font-medium text-foreground">上传参考文件（可选）</label>
                        <input
                          type="file"
                          multiple
                          onChange={e => setUploadedFiles(e.target.files)}
                          disabled={!!selectedTemplateId}
                          className="block w-full text-xs file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-primary-foreground disabled:opacity-60 disabled:cursor-not-allowed"
                        />
                        <div className="text-xs text-muted-foreground">
                          已选文件：{uploadedFiles?.length || 0}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2 flex-1 flex flex-col min-h-[280px]">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium text-foreground">项目内容描述</label>
                      <button 
                        type="button" 
                        onClick={fillTemplate} 
                        className="text-xs flex items-center text-primary hover:text-primary/80 transition-colors px-2 py-1 rounded hover:bg-primary/10"
                      >
                        <Sparkles className="h-3 w-3 mr-1" />
                        填充通用格式
                      </button>
                    </div>
                    <textarea 
                      value={desc} 
                      onChange={e => setDesc(e.target.value)} 
                      placeholder="请详细描述访谈目标、对象、核心议题与边界限制..." 
                      rows={16}
                      className="flex-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-none leading-relaxed"
                    />
                  </div>
                </div>
                
                <div className="p-6 border-t border-border bg-muted/10 flex items-center justify-end space-x-3">
                  <button 
                    disabled={loading} 
                    onClick={() => navigate('/')} 
                    className="px-4 py-2 rounded-md text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                  >
                    取消
                  </button>
                  <button 
                    type="button" 
                    onClick={handleCreateClick} 
                    disabled={loading || !name || !desc} 
                    className="inline-flex items-center justify-center rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2 shadow-sm transition-all hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                    {selectedTemplateId ? '创建项目' : '下一步'}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-6 w-full max-w-[1600px] h-full max-h-[calc(100vh-8rem)]">
              <div className="bg-card rounded-xl border border-border shadow-sm flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-500">
                <div className="p-4 border-b border-border flex items-center justify-between bg-muted/10">
                  <div className="flex items-center space-x-2">
                      <CheckCircle className={`h-5 w-5 ${(entropy !== null && entropyThresholdUsed !== null && entropy < entropyThresholdUsed) ? 'text-yellow-500' : 'text-green-500'}`} />
                    <div className="font-semibold text-foreground">访谈信息清晰度评估报告</div>
                  </div>
                  <div className="text-xs font-mono bg-background border border-border px-2 py-1 rounded text-muted-foreground">
                    参考线: {entropyThresholdUsed ?? '-'}
                  </div>
                </div>
                
                <div className="flex-1 overflow-y-auto p-6">
                  {entropy === null ? (
                    <div className="flex flex-col items-center justify-center h-full text-muted-foreground space-y-2">
                      <Loader2 className="h-8 w-8 animate-spin text-primary" />
                      <p>正在生成报告...</p>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* Score Cards */}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="p-4 rounded-lg bg-muted/30 border border-border text-center">
                          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">整体清晰度</div>
                          <div className={`text-2xl font-bold ${(entropy !== null && entropyThresholdUsed !== null && entropy < entropyThresholdUsed) ? 'text-yellow-600' : 'text-green-600'}`}>
                            {entropy.toFixed(3)}
                          </div>
                        </div>
                        <div className="p-4 rounded-lg bg-muted/30 border border-border text-center">
                          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">主题覆盖度</div>
                          <div className="text-2xl font-bold text-foreground">{semanticScore}</div>
                        </div>
                        <div className="p-4 rounded-lg bg-muted/30 border border-border text-center">
                          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">内容充实度</div>
                          <div className="text-2xl font-bold text-foreground">{Math.round((lengthScore||0)*100)}%</div>
                        </div>
                      </div>

                      {/* Content Preview */}
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className="text-sm font-medium text-foreground">结构化访谈概要（可编辑）</label>
                          <button
                            type="button"
                            onClick={saveReviewEdit}
                            disabled={reviewSaving}
                            className="px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors text-xs font-medium inline-flex items-center"
                          >
                            {reviewSaving ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Save className="h-3.5 w-3.5 mr-1.5" />}
                            保存并重新评估
                          </button>
                        </div>
                        <textarea
                          value={reviewDraft}
                          onChange={e => setReviewDraft(e.target.value)}
                          rows={18}
                          className="w-full rounded-lg border border-input bg-background px-3 py-3 text-sm text-foreground/90 leading-relaxed font-mono resize-y min-h-[300px] max-h-[560px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        />
                      </div>

                      {/* Alert for low score */}
                      {(entropy !== null && entropyThresholdUsed !== null && entropy < entropyThresholdUsed) && (
                        <div className="p-4 rounded-lg bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-900/50 flex items-start space-x-3">
                          <Sparkles className="h-5 w-5 text-yellow-600 dark:text-yellow-500 mt-0.5 shrink-0" />
                          <div>
                            <h4 className="text-sm font-medium text-yellow-800 dark:text-yellow-400">建议补充</h4>
                            <p className="text-xs text-yellow-700 dark:text-yellow-500/80 mt-1">
                              当前内容还可以更具体，建议补充访谈目标、对象、关键议题和边界限制，以提升后续框架质量。
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                
                <div className="p-4 border-t border-border bg-muted/10 flex items-center justify-end space-x-3">
                  <button 
                    onClick={confirmAndCreate} 
                    disabled={loading || retrievalOpen || generatingFramework} 
                    className="px-4 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors text-sm font-medium inline-flex items-center shadow-sm"
                  >
                    {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                    确认并创建项目
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {retrievalOpen && (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm flex items-center justify-center p-4">
           <div className="bg-card border border-border shadow-2xl rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95">
             <div className="p-6 border-b border-border flex justify-between items-center">
               <h3 className="text-lg font-semibold">多路径知识卡片流</h3>
               <button onClick={() => setRetrievalOpen(false)} className="text-muted-foreground hover:text-foreground">
                 <Plus className="h-6 w-6 rotate-45" />
               </button>
             </div>
             <div className="p-6 overflow-y-auto flex-1 space-y-4">
               {retrievalError && <div className="p-3 bg-destructive/10 text-destructive rounded-md text-sm">{retrievalError}</div>}
               {retrievalLoading ? (
                <div className="py-8 space-y-4">
                  <div className="flex items-center justify-center">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>{retrievalStageText || '处理中...'}</span>
                      <span>{Math.round(retrievalProgress)}%</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                      <div className="h-full bg-primary transition-all duration-300" style={{ width: `${Math.max(0, Math.min(100, retrievalProgress))}%` }} />
                    </div>
                  </div>
                </div>
               ) : (
                 <div className="space-y-4">
                   <div className="flex justify-between items-center bg-gradient-to-r from-muted/40 via-muted/20 to-background p-4 rounded-xl border border-border">
                    <span className="text-sm text-muted-foreground">检索阈值: {retrievalThresholdUsed ?? '-'} / 模式: {knowledgeMode === 'none' ? '无领域经验' : knowledgeMode.toUpperCase()} / 卡片总数: {retrievalCandidates.length}</span>
                     <button onClick={recomputeRetrieval} className="text-sm text-primary hover:underline flex items-center"><RefreshCcw className="h-3 w-3 mr-1"/>重新获取</button>
                   </div>
                   {retrievalCandidates.length === 0 ? (
                    <div className="text-center py-10 text-muted-foreground">当前没有可用知识卡片，将直接基于当前访谈背景生成访谈框架。</div>
                   ) : (
                     <div className="space-y-3">
                       {groupedRetrievalCandidates.map(group => {
                         const collapsed = collapsedSources[group.source] ?? false
                         return (
                           <div key={group.source} className="rounded-xl border border-border overflow-hidden bg-card">
                             <button
                               type="button"
                               onClick={() => toggleSourceCollapse(group.source)}
                               className="w-full p-4 bg-muted/20 hover:bg-muted/30 transition-colors flex items-center justify-between text-left"
                             >
                               <div className="space-y-1">
                                 <div className="font-medium text-foreground">{sourceLabel(group.source)}</div>
                                 <div className="text-xs text-muted-foreground">{getSourceOverview(group.source, group.items)}</div>
                               </div>
                               <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${collapsed ? '-rotate-90' : 'rotate-0'}`} />
                             </button>
                             {!collapsed && (
                               <div className="p-3 space-y-3 bg-background/50">
                                 {group.items.map(({ item, index }) => {
                                   const isEditing = !!editingCardIndexes[index]
                                   const draft = editingDrafts[index] || item
                                   return (
                                     <div key={`${group.source}-${index}`} className="border border-border rounded-lg p-4 bg-card shadow-sm hover:shadow-md transition-all">
                                       <div className="flex justify-between items-start gap-3 mb-3">
                                         <div className="min-w-0 flex-1">
                                           {isEditing ? (
                                             <input
                                               value={draft.title || ''}
                                               onChange={e => updateEditDraft(index, { title: e.target.value })}
                                               className="font-medium bg-transparent border-b border-border/60 focus:outline-none focus:border-primary min-w-0 w-full"
                                             />
                                           ) : (
                                             <div className="font-medium break-words">{item.title || '未命名知识卡片'}</div>
                                           )}
                                         </div>
                                         <div className="flex items-center gap-1.5 shrink-0">
                                           <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded-full">
                                             {sourceLabel(item.source)}
                                           </span>
                                           {isEditing ? (
                                             <>
                                               <button type="button" onClick={() => saveEditCard(index)} className="h-8 w-8 rounded-md border border-border hover:bg-primary/10 text-primary flex items-center justify-center">
                                                 <Save className="h-4 w-4" />
                                               </button>
                                               <button type="button" onClick={() => cancelEditCard(index)} className="h-8 w-8 rounded-md border border-border hover:bg-muted text-muted-foreground flex items-center justify-center">
                                                 <X className="h-4 w-4" />
                                               </button>
                                             </>
                                           ) : (
                                             <button type="button" onClick={() => startEditCard(index)} className="h-8 w-8 rounded-md border border-border hover:bg-primary/10 text-primary flex items-center justify-center">
                                               <Pencil className="h-4 w-4" />
                                             </button>
                                           )}
                                           <button type="button" onClick={() => deleteCard(index)} className="h-8 w-8 rounded-md border border-border hover:bg-destructive/10 text-destructive flex items-center justify-center">
                                             <Trash2 className="h-4 w-4" />
                                           </button>
                                         </div>
                                       </div>
                                       {typeof item.similarity === 'number' && (
                                         <div className="text-xs text-muted-foreground mb-2">相似度：{(item.similarity * 100).toFixed(1)}%</div>
                                       )}
                                       <div className="flex flex-wrap gap-2 mb-2 items-center">
                                         {(item.reference || '').startsWith('http') && (
                                           <a
                                             href={item.reference}
                                             target="_blank"
                                             rel="noreferrer"
                                             className="text-[10px] px-2 py-0.5 rounded border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100"
                                           >
                                             {item.reference}
                                           </a>
                                         )}
                                         {isEditing ? (
                                           <input
                                             value={(draft.tags || []).join(',')}
                                             onChange={e => updateEditDraft(index, { tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })}
                                             placeholder="标签，逗号分隔"
                                             className="text-xs flex-1 min-w-[220px] rounded border border-input bg-background px-2 py-1"
                                           />
                                         ) : (
                                           <div className="flex flex-wrap gap-1.5">
                                             {(item.tags || []).map((tag, idx) => (
                                               <span key={`${group.source}-${index}-tag-${idx}`} className="text-[10px] px-2 py-0.5 rounded-full border border-border bg-muted/30 text-muted-foreground">#{tag}</span>
                                             ))}
                                           </div>
                                         )}
                                       </div>
                                       {isEditing ? (
                                         <>
                                           <textarea
                                             value={draft.key_insights || ''}
                                             onChange={e => updateEditDraft(index, { key_insights: e.target.value })}
                                             placeholder="核心观点"
                                             rows={3}
                                             className="text-sm w-full rounded border border-input bg-background px-3 py-2"
                                           />
                                           <textarea
                                             value={draft.content || ''}
                                             onChange={e => updateEditDraft(index, { content: e.target.value })}
                                             placeholder="详细内容"
                                             rows={8}
                                             className="text-sm w-full rounded border border-input bg-background px-3 py-2 mt-2 whitespace-pre-wrap"
                                           />
                                         </>
                                       ) : (
                                         <div className="space-y-2">
                                           {(item.key_insights || '').trim() && (
                                             <div className="text-sm rounded-md border border-border bg-muted/20 px-3 py-2 whitespace-pre-wrap">
                                               {item.key_insights}
                                             </div>
                                           )}
                                           <div className="text-sm rounded-md border border-border bg-background px-3 py-2 whitespace-pre-wrap">
                                             {item.content || '暂无内容'}
                                           </div>
                                         </div>
                                       )}
                                     </div>
                                   )
                                 })}
                               </div>
                             )}
                           </div>
                         )
                       })}
                     </div>
                   )}
                 </div>
               )}
             </div>
             <div className="p-6 border-t border-border bg-muted/10 flex justify-between items-center">
              <label className="text-sm text-muted-foreground flex items-center gap-2">
                <input type="checkbox" checked={saveKnowledgeToLibrary} onChange={e => setSaveKnowledgeToLibrary(e.target.checked)} />
                本次融合后一键保存到知识库
              </label>
              <button onClick={generateWithFused} disabled={generatingFramework} className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:bg-primary/90 flex items-center">
                {generatingFramework && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                汇总知识并生成框架
              </button>
            </div>
           </div>
        </div>
      )}
    </div>
  )
}
