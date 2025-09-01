import com.atlassian.jira.component.ComponentAccessor
import groovy.json.JsonOutput
import java.net.URL
import java.nio.charset.StandardCharsets

// куда отправляем
final String BOT_URL = "http://localhost:8081/jira-webhook"

// достаём значение поля "Отдел"
def cfm = ComponentAccessor.getCustomFieldManager()
def deptCf = cfm.getCustomFieldObject("customfield_10100") // <-- замени, если у тебя другой ID
def deptVal = issue.getCustomFieldValue(deptCf)
def dept = (deptVal?.hasProperty('value')) ? deptVal.value : (deptVal?.toString())

// соберём payload в формате, который бот понимает
def payload = [
  issue: [
    key   : issue.key,
    fields: [
      // сервер поймёт и строку, и объект {value: "..."}
      (deptCf.id): dept ? [value: dept] : null
    ]
  ],
  webhookEvent: event?.getClass()?.simpleName ?: "Unknown"
]

def conn = new URL(BOT_URL).openConnection()
conn.setRequestMethod("POST")
conn.setDoOutput(true)
conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8")

def bytes = JsonOutput.toJson(payload).getBytes(StandardCharsets.UTF_8)
conn.getOutputStream().write(bytes)

int code = conn.getResponseCode()
// можно посмотреть в журнале ScriptRunner, что вернул бот
log.info("IT-Registry: webhook -> ${BOT_URL} responded HTTP ${code}")
