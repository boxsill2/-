// f1api.js (server.js와 통합된 버전)
const fs = require('fs');
const path = require('path');
const express = require('express');
const { spawn } = require('child_process');

// --- Express 앱 및 라우터 초기화 ---
const app = express();
const router = express.Router();

const ROOT_DIR = __dirname;
const PUBLIC_DIR = path.join(ROOT_DIR, 'public');
const DATA_DIR = path.join(PUBLIC_DIR, 'data');

// --- 뷰 엔진 및 정적 파일 경로 설정 ---
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.static(path.join(__dirname, 'public')));


// --- Helper 함수들 ---
async function readJSON(filePath) { try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); } catch { return null; } }
function slugify(text) { return String(text || '').toLowerCase().trim().replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-'); }

function runPython(scriptPath, args = []) {
    return new Promise((resolve, reject) => {
        if (!fs.existsSync(scriptPath)) {
            return reject(new Error(`Python script not found: ${scriptPath}`));
        }

        const pythonProcess = spawn('python', ['-X', 'utf8', scriptPath, ...args]);
        let stdout = '';
        let stderr = '';

        pythonProcess.stdout.setEncoding('utf8');
        pythonProcess.stdout.on('data', (data) => { stdout += data.toString(); });
        pythonProcess.stderr.on('data', (data) => { stderr += data.toString(); });

        pythonProcess.on('close', (code) => {
            if (stderr) console.error(`[Python STDERR]: ${stderr.trim()}`);
            if (code !== 0) {
                const errorMsg = stderr.trim() || `Python script exited with code ${code}`;
                return reject(new Error(errorMsg));
            }
            resolve(stdout);
        });
    });
}

async function fetchRaceTimingFromPython(sessionInfo) {
    const scriptPath = path.join(ROOT_DIR, 'get_replay_data.py');
    try {
        if (!sessionInfo) throw new Error('Session info cannot be null.');

        let year = sessionInfo.session_year;
        if ((!year || year === 'undefined') && sessionInfo.date_start) {
            year = new Date(sessionInfo.date_start).getFullYear();
        }

        const eventName = sessionInfo.meeting_name;
        const sessionName = sessionInfo.session_name;

        if (!year || !eventName || !sessionName) {
            throw new Error(`Incomplete session data from schedule.json: Year='${year}', Event='${eventName}', Session='${sessionName}'`);
        }

        const args = [
            'race_times',
            '--year', String(year),
            '--event', eventName,
            '--session', sessionName
        ];

        const rawOutput = await runPython(scriptPath, args);
        const parsed = JSON.parse(rawOutput);
        if (parsed?.error) throw new Error(parsed.error);
        return parsed;
    } catch (error) {
        console.error(`[Race Timing Fetch Error]: ${error.message}`);
        throw error;
    }
}


// --- 라우팅 설정 ---
router.get('/', (req, res) => res.redirect('/schedule'));

router.get('/schedule', async (req, res) => {
    try {
        const schedule = await readJSON(path.join(DATA_DIR, 'schedule.json'));
        res.render('schedule', { year: new Date().getFullYear(), schedule: schedule || [], error: null, currentPage: 'schedule' });
    } catch (e) { res.render('schedule', { year: new Date().getFullYear(), schedule: [], error: '스케줄 데이터를 불러오지 못했습니다.', currentPage: 'schedule' }); }
});

router.get('/drivers', async (req, res) => {
    try {
        const drivers = await readJSON(path.join(DATA_DIR, 'drivers.json'));
        res.render('drivers', { drivers: drivers || [], currentPage: 'drivers', error: null, slugify });
    } catch (e) {
        res.status(500).render('drivers', { drivers: [], error: '드라이버 데이터를 불러오는 데 실패했습니다.', currentPage: 'drivers', slugify });
    }
});

router.get('/drivers/:driverId', async (req, res) => {
    try {
        const { driverId } = req.params;
        const drivers = await readJSON(path.join(DATA_DIR, 'drivers.json'));
        const driver = drivers.find(d => slugify(d.full_name) === driverId);

        if (!driver) {
            return res.status(404).render('driver-detail', { info: null, description: null, season: {}, career: {}, error: '드라이버 정보를 찾을 수 없습니다.', currentPage: 'drivers', slugify });
        }

        const driverDescriptions = await readJSON(path.join(DATA_DIR, 'driver_descriptions.json'));
        const description = driverDescriptions[driver.full_name] || '이 드라이버에 대한 추가 정보가 없습니다.';
        
        let driverStats = await readJSON(path.join(DATA_DIR, 'stats', `${slugify(driver.full_name)}.json`));
        
        const seasonStats = driverStats?.season || {};
        const careerStats = driverStats?.career || {};

        res.render('driver-detail', { 
            info: driver, 
            description, 
            season: seasonStats, 
            career: careerStats, 
            error: null, 
            currentPage: 'drivers',
            slugify
        });
    } catch (e) {
        console.error(e);
        res.status(500).render('driver-detail', { info: null, description: null, season: {}, career: {}, error: '드라이버 데이터를 불러오는 데 실패했습니다.', currentPage: 'drivers', slugify });
    }
});

router.get('/teams', async (req, res) => {
    try {
        const teams = await readJSON(path.join(DATA_DIR, 'teams.json'));
        res.render('teams', { teams: teams || [], currentPage: 'teams', error: null });
    } catch (e) {
        res.status(500).render('teams', { teams: [], error: '팀 데이터를 불러오는 데 실패했습니다.', currentPage: 'teams' });
    }
});

router.get('/teams/:teamId', async (req, res) => {
    try {
        const { teamId } = req.params;
        const teams = await readJSON(path.join(DATA_DIR, 'teams.json'));
        const team = teams.find(t => t.slug === teamId);

        if (!team) {
            return res.status(404).render('team-detail', { info: null, drivers: [], error: '팀 정보를 찾을 수 없습니다.', currentPage: 'teams', slugify });
        }
        
        const drivers = await readJSON(path.join(DATA_DIR, 'drivers.json'));
        const teamDrivers = drivers.filter(d => d.team_name === team.team_name);

        res.render('team-detail', { info: team, drivers: teamDrivers, error: null, currentPage: 'teams', slugify });
    } catch (e) {
        console.error(e);
        res.status(500).render('team-detail', { info: null, drivers: [], error: '팀 데이터를 불러오는 데 실패했습니다.', currentPage: 'teams', slugify });
    }
});

router.get('/glossary', async (req, res) => {
    try {
        const terms = await readJSON(path.join(ROOT_DIR, 'f1_terms.json'));
        res.render('glossary', { terms: terms || [], currentPage: 'glossary', error: null });
    } catch (e) {
        res.status(500).render('glossary', { terms: [], error: '용어 데이터를 불러오는 데 실패했습니다.', currentPage: 'glossary' });
    }
});

router.get('/replays/:session_key', async (req, res) => {
    const { session_key } = req.params;
    try {
        const schedule = await readJSON(path.join(DATA_DIR, 'schedule.json'));
        const layouts = await readJSON(path.join(DATA_DIR, 'track_layouts.json'));
        const sessionInfo = schedule?.find(s => String(s.session_key) === session_key) || null;

        if (!sessionInfo) {
            return res.status(404).render('race-tracker', { error: '해당 세션 정보를 찾을 수 없습니다.' });
        }

        const circuitName = sessionInfo.circuit_short_name?.toLowerCase().replace(/\s+/g, '-');
        const layout = layouts?.find(l => l.circuit_short_name === circuitName);

        let trackImageUrl = null;
        if (circuitName) {
            const possibleExtensions = ['avif', 'png', 'webp', 'jpg', 'jpeg'];
            for (const ext of possibleExtensions) {
                const imageName = `${circuitName}.${ext}`;
                const imagePath = path.join(PUBLIC_DIR, 'images', 'tracks', imageName);
                if (fs.existsSync(imagePath)) {
                    trackImageUrl = `/images/tracks/${imageName}`;
                    break;
                }
            }
        }

        const [drivers, f1Teams, raceTiming] = await Promise.all([
            readJSON(path.join(DATA_DIR, 'drivers.json')),
            readJSON(path.join(ROOT_DIR, 'f1_team.json')),
            fetchRaceTimingFromPython(sessionInfo)
        ]);
        const driverDirectory = {};
        if (drivers && f1Teams) {
            const teamInfoMap = f1Teams.reduce((acc, team) => { acc[team.name] = { color: team.teamColor }; return acc; }, {});
            drivers.forEach(d => { if (d.number) driverDirectory[d.number] = { full_name: d.full_name, team_colour: teamInfoMap[d.team_name]?.color || '#FFFFFF' }; });
        }

        const finalSessionInfo = { ...sessionInfo, trackImageUrl, layout };
        if (raceTiming?.race_start_date) {
            finalSessionInfo.date_start = raceTiming.race_start_date;
        }
        if (raceTiming?.race_end_date) {
            finalSessionInfo.race_end_date = raceTiming.race_end_date;
        }
        if (raceTiming?.all_messages) {
            finalSessionInfo.race_control_messages = raceTiming.all_messages;
        }

        res.render('race-tracker', {
            session_key,
            driverDirectory,
            sessionInfo: finalSessionInfo,
            currentPage: 'schedule',
            error: null
        });
    } catch (e) {
        console.error(e);
        res.status(500).render('race-tracker', { session_key, driverDirectory: {}, sessionInfo: null, error: `페이지 로드 중 오류 발생: ${e.message}`, currentPage: 'schedule' });
    }
});

router.get('/api/locations/:session_key/:startTime/:endTime', async (req, res) => {
    const { session_key, startTime, endTime } = req.params;
    try {
        const schedule = await readJSON(path.join(DATA_DIR, 'schedule.json'));
        const sessionInfo = schedule?.find(s => String(s.session_key) === session_key);

        if (!sessionInfo) {
            return res.status(404).json({ error: 'Session info not found for the given key.' });
        }

        let year = sessionInfo.session_year;
        if ((!year || year === 'undefined') && sessionInfo.date_start) {
            year = new Date(sessionInfo.date_start).getFullYear();
        }
        
        const eventName = sessionInfo.meeting_name;
        const sessionName = sessionInfo.session_name;

        if (!year || !eventName || !sessionName) {
            return res.status(500).json({ error: 'Incomplete session data to fetch locations.' });
        }
        
        const scriptPath = path.join(ROOT_DIR, 'get_driver_locations.py');
        if (!fs.existsSync(scriptPath)) {
            return res.status(500).json({ error: 'get_driver_locations.py 스크립트를 찾을 수 없습니다.' });
        }

        const args = [
            String(year),
            eventName,
            sessionName,
            startTime,
            endTime
        ];
        
        const output = await runPython(scriptPath, args);
        res.json(JSON.parse(output));

    } catch (error) {
        console.error(`[API Locations Error]: ${error.message}`);
        res.status(500).json({ error: `Internal server error while fetching locations: ${error.message}` });
    }
});


// --- 라우터를 앱에 적용 ---
app.use('/', router);


// --- 서버 실행 ---
const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`서버가 http://localhost:${PORT} 에서 시작되었습니다.`);
});