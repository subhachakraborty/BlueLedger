wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"

math.randomseed(os.time())

request = function()
  local id = math.random(1000000)

  local body = string.format(
    '{"firstname":"user%d","lastname":"test","email":"user%d@test.com","password":"password123"}',
    id, id
  )

  return wrk.format("POST", "/signup", nil, body)
end
