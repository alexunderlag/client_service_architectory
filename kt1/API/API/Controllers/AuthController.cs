using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.SignalR;
using API.Hubs;
using API.Data;
using API.Models;

namespace API.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class AuthController : ControllerBase
    {
        private static Dictionary<string, DateTime> _sessions = new Dictionary<string, DateTime>();
        private readonly IHubContext<UserHub> _hubContext;
        private readonly UserRepository _repository;

        public AuthController(IHubContext<UserHub> hubContext)
        {
            _hubContext = hubContext;
            _repository = new UserRepository();
        }

        [HttpPost("login")]
        public IActionResult Login(string username)
        {
            var sessionId = Guid.NewGuid().ToString();
            _sessions[sessionId] = DateTime.UtcNow.AddMinutes(1); 

            var user = _repository.GetAll().FirstOrDefault(u => u.Name == username);
            if (user != null)
            {
                user.IsOnline = true;
                _hubContext.Clients.All.SendAsync("ReceiveUserStatus", user.Id, true);
            }

            return Ok(new { SessionId = sessionId });
        }

        [HttpPost("logout")]
        public IActionResult Logout(string sessionId)
        {
            if (_sessions.ContainsKey(sessionId))
            {
                _sessions.Remove(sessionId);

                var user = _repository.GetAll().FirstOrDefault(u => u.IsOnline);
                if (user != null)
                {
                    user.IsOnline = false;
                    _hubContext.Clients.All.SendAsync("ReceiveUserStatus", user.Id, false);
                }

                return Ok();
            }
            return Unauthorized();
        }
    }
}
