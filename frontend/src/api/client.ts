export async function apiGet(url: string) {
  const res = await fetch(url)
  if (!res.ok) throw new Error(String(res.status))
  return res.json()
}

export async function apiPost(url: string, body: Record<string, unknown>) {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!res.ok) throw new Error(String(res.status))
  return res.json()
}

export async function apiPatch(url: string, body: Record<string, unknown>) {
  const res = await fetch(url, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!res.ok) throw new Error(String(res.status))
  return res.json()
}

export async function apiDelete(url: string) {
  const res = await fetch(url, { method: 'DELETE' })
  if (!res.ok) throw new Error(String(res.status))
  return res.json()
}

export function getUserIdFromStorage(): number | undefined {
  const userRaw = localStorage.getItem('user')
  if (!userRaw) return undefined
  try {
    const user = JSON.parse(userRaw) as { user_id?: number }
    if (typeof user.user_id === 'number' && Number.isFinite(user.user_id)) return user.user_id
  } catch {
    return undefined
  }
  return undefined
}

function buildScopedKey(key: string, user_id?: number) {
  return typeof user_id === 'number' ? `user_${user_id}_${key}` : key
}

export function getScopedLocalValue(key: string, user_id?: number) {
  const uid = user_id ?? getUserIdFromStorage()
  if (typeof uid === 'number') {
    const scoped = localStorage.getItem(buildScopedKey(key, uid))
    if (scoped !== null) return scoped
  }
  return null
}

export function setScopedLocalValue(key: string, value: string, user_id?: number) {
  const uid = user_id ?? getUserIdFromStorage()
  if (typeof uid !== 'number') return
  const finalKey = buildScopedKey(key, uid)
  localStorage.setItem(finalKey, value)
}

export async function getUserLLMConfig(user_id: number) {
  return apiGet(`/api/users/${user_id}/llm-config`)
}

export async function saveUserLLMConfig(user_id: number, config: { api_url: string; api_key: string; model_name: string; embedding_api_url: string; embedding_api_key: string; embedding_model_name: string }) {
  return apiPost(`/api/users/${user_id}/llm-config`, config)
}

export async function getProjects(user_id?: number) {
  const uid = user_id ?? getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects?user_id=${uid}` : '/api/projects'
  return apiGet(url)
}

export async function createProject(project_name: string, initial_requirements: string, domain_ids?: number[] | null, user_id?: number | null) {
  const uid = typeof user_id === 'number' ? user_id : getUserIdFromStorage()
  const body: Record<string, unknown> = { project_name, initial_requirements }
  if (Array.isArray(domain_ids)) body.domain_ids = domain_ids
  if (typeof uid === 'number') body.user_id = uid
  return apiPost('/api/projects', body)
}

export async function updateProject(project_id: number, data: Record<string, unknown>) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects/${project_id}?user_id=${uid}` : `/api/projects/${project_id}`
  return apiPatch(url, data)
}

export async function deleteProject(project_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects/${project_id}?user_id=${uid}` : `/api/projects/${project_id}`
  return apiDelete(url)
}

export async function getStructure(project_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects/${project_id}/structure?user_id=${uid}` : `/api/projects/${project_id}/structure`
  return apiGet(url)
}

export type LLMConfig = { api_url: string; api_key: string; model_name: string }
export function getLLMConfigFromStorage(): LLMConfig | null {
  const uid = getUserIdFromStorage()
  if (typeof uid !== 'number') return null
  const api_url = localStorage.getItem(buildScopedKey('llm_api_url', uid)) || ''
  const api_key = localStorage.getItem(buildScopedKey('llm_api_key', uid)) || ''
  const model_name = localStorage.getItem(buildScopedKey('llm_model_name', uid)) || ''
  if (!api_url || !api_key || !model_name) return null
  return { api_url, api_key, model_name }
}
export type EmbedConfig = { api_url: string; api_key: string; model_name: string }
export function getEmbedConfigFromStorage(): EmbedConfig | null {
  const uid = getUserIdFromStorage()
  if (typeof uid !== 'number') return null
  const api_url = localStorage.getItem(buildScopedKey('embedding_api_url', uid)) || ''
  const api_key = localStorage.getItem(buildScopedKey('embedding_api_key', uid)) || ''
  const model_name = localStorage.getItem(buildScopedKey('embedding_model_name', uid)) || ''
  if (!api_url || !api_key || !model_name) return null
  return { api_url, api_key, model_name }
}
export async function initializeFramework(project_id: number, config: LLMConfig) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { ...config }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/initialize`, body)
}

export async function listDomainExperiences(user_id?: number, options?: { sharedOnly?: boolean; includeShared?: boolean }) {
  const params = new URLSearchParams()
  if (typeof user_id === 'number') params.set('user_id', String(user_id))
  if (options?.sharedOnly) params.set('shared_only', 'true')
  if (options?.includeShared) params.set('include_shared', 'true')
  const qs = params.toString()
  const url = qs ? `/api/domain-experiences?${qs}` : `/api/domain-experiences`
  return apiGet(url)
}

export async function createDomainExperience(data: Record<string, unknown>) {
  return apiPost(`/api/domain-experiences`, data)
}

export async function updateDomainExperience(domain_id: number, data: Record<string, unknown>) {
  return apiPatch(`/api/domain-experiences/${domain_id}`, data)
}

export async function deleteDomainExperience(domain_id: number) {
  return apiDelete(`/api/domain-experiences/${domain_id}`)
}

export async function recomputeDomainEmbedding(domain_id: number, api_key: string, api_url: string, model_name: string, text_override?: string) {
  return apiPost(`/api/domain-experiences/${domain_id}/embedding/recompute`, { api_key, api_url, model_name, text_override })
}

export async function recomputeAllDomainEmbeddings(api_key: string, api_url: string, model_name: string, user_id?: number) {
  return apiPost(`/api/domain-experiences/embedding/recompute-all`, { api_key, api_url, model_name, user_id })
}

export async function ingestCreateDomainExperience(fd: FormData) {
  const res = await fetch(`/api/domain-experiences/ingest-create`, { method: 'POST', body: fd })
  if (!res.ok) throw new Error(String(res.status))
  return res.json()
}

export async function getProjectChat(project_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects/${project_id}/chat?user_id=${uid}` : `/api/projects/${project_id}/chat`
  return apiGet(url)
}

export async function startInterview(project_id: number, config: LLMConfig) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { ...config }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/interview/start`, body)
}

export async function sendReply(project_id: number, config: LLMConfig, text: string, embed?: EmbedConfig | null) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { ...config, text }
  if (embed) {
    body.embed_api_url = embed.api_url
    body.embed_api_key = embed.api_key
    body.embed_model_name = embed.model_name
  }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/interview/reply`, body)
}

export async function getProjectDetail(project_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects/${project_id}?user_id=${uid}` : `/api/projects/${project_id}`
  return apiGet(url)
}

export async function regenerateReport(project_id: number, llm?: LLMConfig | null, embed?: EmbedConfig | null) {
  const body: Record<string, unknown> = {}
  if (llm) {
    body.llm_api_url = llm.api_url
    body.llm_api_key = llm.api_key
    body.llm_model_name = llm.model_name
  }
  if (embed) {
    body.embed_api_url = embed.api_url
    body.embed_api_key = embed.api_key
    body.embed_model_name = embed.model_name
  }
  const uid = getUserIdFromStorage()
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/report/regenerate`, body)
}

export async function downloadReport(project_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects/${project_id}/report/download?user_id=${uid}` : `/api/projects/${project_id}/report/download`
  const res = await fetch(url)
  if (!res.ok) throw new Error(String(res.status))
  const blob = await res.blob()
  return blob
}

export async function downloadChat(project_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects/${project_id}/chat/download?user_id=${uid}` : `/api/projects/${project_id}/chat/download`
  const res = await fetch(url)
  if (!res.ok) throw new Error(String(res.status))
  const blob = await res.blob()
  return blob
}

export async function downloadSlots(project_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/projects/${project_id}/slots/download?user_id=${uid}` : `/api/projects/${project_id}/slots/download`
  const res = await fetch(url)
  if (!res.ok) throw new Error(String(res.status))
  const blob = await res.blob()
  return blob
}

export async function evaluateEntropy(config: LLMConfig, text: string) {
  return apiPost(`/api/projects/entropy-evaluate`, { ...config, text })
}

export async function getConfigValues() {
  return apiGet(`/api/config`)
}

export async function retrievalSuggest(project_id: number, embed: { api_url: string; api_key: string; model_name: string }, user_id?: number | null) {
  const uid = typeof user_id === 'number' ? user_id : getUserIdFromStorage()
  return apiPost(`/api/projects/${project_id}/retrieval/suggest`, { ...embed, user_id: uid })
}

export async function initializeFrameworkWithFused(project_id: number, config: LLMConfig, fused_text: string) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { ...config, fused_text }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/initialize-with-fused`, body)
}

// New endpoints to support pre-creation retrieval and atomic project creation
export async function retrievalSuggestFromText(text: string, embed: { api_url: string; api_key: string; model_name: string }, threshold?: number, top_k?: number, user_id?: number | null) {
  const body: Record<string, unknown> = { ...embed, text }
  if (typeof threshold === 'number') body.threshold = threshold
  if (typeof top_k === 'number') body.top_k = top_k
  const uid = typeof user_id === 'number' ? user_id : getUserIdFromStorage()
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/retrieval/suggest-text`, body)
}

export type KnowledgeMode = 'basic' | 'pro' | 'max'
export type KnowledgeItem = {
  source: 'DB_RETRIEVAL' | 'WEB_SEARCH' | 'LLM_GEN' | 'FILE_UPLOAD' | string
  title: string
  key_insights: string
  content: string
  tags: string[]
  reference: string
  similarity?: number | null
}

export async function acquireKnowledge(
  payload: {
    project_name: string
    initial_requirements: string
    mode: KnowledgeMode
    use_domain_knowledge: boolean
    api_url: string
    api_key: string
    model_name: string
    embedding_api_url?: string
    embedding_api_key?: string
    embedding_model_name?: string
    threshold?: number
    user_id?: number
  }
) {
  return apiPost('/api/knowledge/acquire', payload as unknown as Record<string, unknown>)
}

export async function summarizeKnowledge(
  payload: {
    project_name: string
    initial_requirements: string
    knowledge_items: KnowledgeItem[]
    api_url: string
    api_key: string
    model_name: string
    embedding_api_url?: string
    embedding_api_key?: string
    embedding_model_name?: string
    user_id?: number
    save_to_library?: boolean
  }
) {
  return apiPost('/api/knowledge/summarize', payload as unknown as Record<string, unknown>)
}

export async function parseKnowledgeFiles(fd: FormData) {
  const res = await fetch('/api/knowledge/files/parse', { method: 'POST', body: fd })
  if (!res.ok) throw new Error(String(res.status))
  return res.json()
}

export async function createAndInitializeProject(project_name: string, initial_requirements: string, config: LLMConfig, fused_text?: string, user_id?: number | null, domain_ids?: number[] | null) {
  const uid = typeof user_id === 'number' ? user_id : getUserIdFromStorage()
  const body: Record<string, unknown> = { project_name, initial_requirements, api_url: config.api_url, api_key: config.api_key, model_name: config.model_name, fused_text: fused_text || "" }
  if (typeof uid === 'number') body.user_id = uid
  if (Array.isArray(domain_ids)) body.domain_ids = domain_ids
  return apiPost(`/api/projects/create-and-initialize`, body)
}

export async function getPriority(project_id: number, config: LLMConfig) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { ...config }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/topics/priority`, body)
}

export async function createSection(project_id: number, section_number: string, section_content: string) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { section_number, section_content }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/sections`, body)
}

export async function updateSection(section_id: number, data: Record<string, unknown>) {
  return apiPatch(`/api/sections/${section_id}`, data)
}

export async function deleteSection(section_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/sections/${section_id}?user_id=${uid}` : `/api/sections/${section_id}`
  return apiDelete(url)
}

export async function createTopic(section_id: number, topic_number: string, topic_content: string, topic_status: string) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { topic_number, topic_content, topic_status }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/sections/${section_id}/topics`, body)
}

export async function updateTopic(topic_id: number, data: Record<string, unknown>) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/topics/${topic_id}?user_id=${uid}` : `/api/topics/${topic_id}`
  return apiPatch(url, data)
}

export async function deleteTopic(topic_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/topics/${topic_id}?user_id=${uid}` : `/api/topics/${topic_id}`
  return apiDelete(url)
}

export async function createSlot(topic_id: number, slot_number: string, slot_key: string, slot_value: string | null, is_necessary: boolean) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { slot_number, slot_key, slot_value, is_necessary }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/topics/${topic_id}/slots`, body)
}

export async function updateSlot(slot_id: number, data: Record<string, unknown>) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/slots/${slot_id}?user_id=${uid}` : `/api/slots/${slot_id}`
  return apiPatch(url, data)
}

export async function deleteSlot(slot_id: number) {
  const uid = getUserIdFromStorage()
  const url = typeof uid === 'number' ? `/api/slots/${slot_id}?user_id=${uid}` : `/api/slots/${slot_id}`
  return apiDelete(url)
}


// Framework Templates
export async function listFrameworkTemplates(user_id?: number, options?: { sharedOnly?: boolean; includeShared?: boolean }) {
  const params = new URLSearchParams()
  if (typeof user_id === 'number') params.set('user_id', String(user_id))
  if (options?.sharedOnly) params.set('shared_only', 'true')
  if (options?.includeShared) params.set('include_shared', 'true')
  const qs = params.toString()
  const url = qs ? `/api/templates?${qs}` : `/api/templates`
  return apiGet(url)
}

export async function createFrameworkTemplate(data: Record<string, unknown>) {
  return apiPost(`/api/templates`, data)
}

export async function updateFrameworkTemplate(template_id: number, data: Record<string, unknown>) {
  return apiPatch(`/api/templates/${template_id}`, data)
}

export async function deleteFrameworkTemplate(template_id: number) {
  return apiDelete(`/api/templates/${template_id}`)
}

export async function saveFrameworkTemplateFromProject(project_id: number, template_name: string, template_description?: string, is_shared?: boolean) {
  return apiPost(`/api/templates/save-from-project/${project_id}`, { template_name, template_description, is_shared })
}

export async function initializeProjectWithTemplate(project_id: number, template_id: number) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { template_id }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/initialize-with-template`, body)
}

export async function prefillFromInitial(project_id: number, config: LLMConfig) {
  const uid = getUserIdFromStorage()
  const body: Record<string, unknown> = { ...config }
  if (typeof uid === 'number') body.user_id = uid
  return apiPost(`/api/projects/${project_id}/prefill-from-initial`, body)
}
