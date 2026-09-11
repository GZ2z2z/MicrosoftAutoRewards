// 真实高质量中英文搜索词库，避免随机乱码被微软风控识别
const SEARCH_WORDS_ZH = [
  // 科技与前沿
  "量子计算机工作原理", "人工智能大模型最新进展", "固态电池商用时间", "核聚变点火技术突破",
  "火星探测最新发现", "詹姆斯韦伯太空望远镜深空图像", "脑机接口应用前景", "常温超导研究现状",
  "自动驾驶等级划分与技术", "光刻机内部构造与原理", "星链卫星网络覆盖范围", "石墨烯材料应用领域",
  "RISC-V架构发展趋势", "微型核反应堆技术", "深海载人潜水器奋斗者号", "仿生机器人灵巧手研发",
  "碳化硅半导体功率器件", "空间站微重力科学实验", "基因编辑技术CRISPR前景", "合成生物学应用案例",
  
  // 自然科学与地理
  "地球磁场倒转历史", "马里亚纳海沟最深处生物", "黑洞蒸发霍金辐射解释", "太阳系外宜居行星列表",
  "板块构造学说演变历史", "寒武纪生命大爆发原因", "南极冰架崩塌最新观测", "厄尔尼诺与拉尼娜现象成因",
  "暗物质与暗能量探测实验", "光速不可超越的物理推导", "宇宙微波背景辐射图景", "深海热泉生态系统",
  "热带雨林生物多样性保护", "世界主要沙漠形成原因", "喜马拉雅山脉隆起历程", "火山喷发类型及成因",
  
  // 历史与文化
  "三星堆青铜面具文化渊源", "丝绸之路历史路线与商贸", "故宫建筑结构榫卯艺术", "敦煌莫高窟壁画艺术价值",
  "文艺复兴三杰代表作品赏析", "古埃及金字塔建造假说", "工业革命对全球经济影响", "汉字演变历史甲骨文到行书",
  "茶文化历史起源与流派", "古希腊哲学派别思想对比", "大航海时代重要地理发现", "宋代城市商业繁荣原因",
  "唐诗宋词文学艺术特色", "秦始皇兵马俑制作工艺", "美索不达米亚文明遗址", "玛雅文明历法与天文学",

  // 生活与健康
  "有氧运动与无氧运动结合方案", "地中海饮食结构特点与健康益处", "深睡眠与浅睡眠生理周期",
  "人体电解质平衡调节机制", "常见维生素与微量元素摄入指南", "间歇性禁食原理与注意事项",
  "室内绿植空气净化效果排行", "咖啡因对神经系统的影响周期", "健康颈椎与腰椎日常保健操",
  "人体免疫系统工作防御流程", "常见过敏原检测与脱敏原理", "眼睛防蓝光与视疲劳缓解技巧",
  
  // 计算机与技术开发
  "Python异步编程asyncio详解", "Chrome扩展插件Manifest V3迁移指南", "嵌入式STM32硬件外设配置",
  "TCP与UDP协议详细对比与应用", "Docker容器原理与镜像构建优化", "Git版本控制分支管理最佳实践",
  "WebSocket长连接心跳机制设计", "Linux常用性能分析排查命令", "关系型与非关系型数据库选型",
  "HTTP/3基于QUIC协议的技术优势", "微服务架构API网关核心功能", "现代前端框架响应式原理",
  
  // 趣味百科与生活常识
  "猫咪呼噜声的生理机制", "为什么彩虹是弧形的物理光学解释", "鸟类长途迁徙导航方式",
  "海水为什么是咸的科学解释", "树木年轮宽窄反映的气候变化", "肥皂泡表面薄膜干涉色彩",
  "蜜蜂如何通过舞蹈传递花源信息", "南极和北极哪个更冷的成因", "变色龙变色的微观晶体机制",
  "极光形成的天文物理条件", "为什么夜晚天空是黑色的奥伯斯佯谬", "回音壁声学反射反射原理"
];

const SEARCH_WORDS_EN = [
  // Science & Technology
  "James Webb space telescope latest discoveries", "how quantum computers solve complex problems",
  "nuclear fusion energy breakthroughs 2026", "advancements in solid-state lithium batteries",
  "mars perseverance rover sample return", "CRISPR gene editing therapy approvals",
  "graphene applications in flexible electronics", "gravitational wave detectors technology",
  "deep sea exploration vehicles and submersibles", "neural network transformer architecture explained",
  "photonic computing and optical processing", "space elevator feasibility and carbon nanotubes",
  
  // Nature & Earth
  "great barrier reef coral restoration", "atmospheric rivers weather phenomenon",
  "plate tectonics and ocean floor spreading", "antarctic ice sheet dynamics and melting",
  "biodiversity hotspots around the globe", "origins of geothermal energy underground",
  "deep sea hydrothermal vents creatures", "monarch butterfly migration navigational compass",
  "photosynthesis quantum coherence research", "aurora borealis magnetic reconnection",
  
  // History & Architecture
  "ancient roman concrete self-healing chemistry", "architectural engineering of gothic cathedrals",
  "industrial revolution socioeconomic changes", "silk road cultural and commercial exchanges",
  "renaissance art perspective and master techniques", "ancient alexandria library historical impact",
  "hagia sophia dome engineering history", "mesopotamian irrigation and agricultural development",
  
  // Health & Daily Knowledge
  "circadian rhythm and melatonin production", "mediterranean diet cardiovascular benefits",
  "aerobic endurance training physiological changes", "essential amino acids daily dietary intake",
  "stages of sleep cycle REM and non-REM", "impact of hydration on cognitive performance",
  
  // Computer Science & Engineering
  "distributed systems consensus algorithms Paxos Raft", "WebAssembly performance advantages in browser",
  "Rust memory safety without garbage collection", "Linux kernel memory management architecture",
  "cryptographic zero-knowledge proofs applications", "REST vs GraphQL architectural patterns"
];

// 辅助函数：根据偏好语言获取随机搜索关键词
function getRandomSearchKeyword(lang = 'mixed') {
  let pool = [];
  if (lang === 'zh') {
    pool = SEARCH_WORDS_ZH;
  } else if (lang === 'en') {
    pool = SEARCH_WORDS_EN;
  } else {
    // 混合语言，70% 中文，30% 英文
    pool = Math.random() < 0.7 ? SEARCH_WORDS_ZH : SEARCH_WORDS_EN;
  }
  const baseWord = pool[Math.floor(Math.random() * pool.length)];

  // 30% 几率附加年份、探索、原理等词缀，让搜索词更自然、多变
  const suffixesZh = ["原理", "最新进展", "科普", "教程", "全景图", "核心技术", "历史背景", "发展历程", "应用案例"];
  const suffixesEn = ["explained", "overview", "latest news", "guide", "fundamentals", "applications", "key concepts"];

  if (Math.random() < 0.3) {
    if (pool === SEARCH_WORDS_ZH) {
      const suf = suffixesZh[Math.floor(Math.random() * suffixesZh.length)];
      if (!baseWord.includes(suf)) {
        return `${baseWord} ${suf}`;
      }
    } else {
      const suf = suffixesEn[Math.floor(Math.random() * suffixesEn.length)];
      if (!baseWord.toLowerCase().includes(suf.toLowerCase())) {
        return `${baseWord} ${suf}`;
      }
    }
  }

  return baseWord;
}

// 导出支持 (同时兼容 importScripts 和 ES module)
if (typeof self !== 'undefined') {
  self.SEARCH_WORDS_ZH = SEARCH_WORDS_ZH;
  self.SEARCH_WORDS_EN = SEARCH_WORDS_EN;
  self.getRandomSearchKeyword = getRandomSearchKeyword;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { SEARCH_WORDS_ZH, SEARCH_WORDS_EN, getRandomSearchKeyword };
}
