// cache-layer.js
const memoryCache = new Map();

function setMemory(key, value, ttl_ms = 3600000) { // 캐시 유지 시간을 1시간으로 늘립니다.
    const expiry = Date.now() + ttl_ms;
    memoryCache.set(key, { value, expiry });
    console.log(`[CACHE SET] Key: ${key}`);
}

function getMemory(key) {
    const entry = memoryCache.get(key);
    if (entry && Date.now() < entry.expiry) {
        console.log(`[CACHE HIT] Key: ${key}`);
        return entry.value;
    }
    if (entry) {
        memoryCache.delete(key); // 만료된 캐시 삭제
    }
    console.log(`[CACHE MISS] Key: ${key}`);
    return null;
}

function makeKey(...args) {
    return args.join(':');
}

module.exports = { setMemory, getMemory, makeKey };