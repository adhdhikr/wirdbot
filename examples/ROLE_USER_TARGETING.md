# Quick Example: Role-Based Campaign

## Send to members with specific roles

Just ask the AI:
> "Create a campaign that sends to everyone with the @Members or @Subscribers role. Add a 'Register' button with a form asking for their email."

The AI will:
1. Create a campaign with target_type='roles'
2. Set target to Members and Subscribers roles
3. Add the button with email form
4. Send it

## Manual Commands

### 1. Create campaign
```
/campaign create target:roles
```

### 2. Set which roles to target
```
/campaign set_targets campaign_id:1 roles:@Members,@Subscribers
```

Or use role IDs:
```
/campaign set_targets campaign_id:1 roles:123456789,987654321
```

### 3. Add button and form
```
/campaign add_button campaign_id:1
```
Then:
```
/campaign add_form form_id:1 modal_title:"Registration" field1_name:email field1_label:"Email Address" response_channel:#registrations
```

### 4. Send
```
/campaign send campaign_id:1
```

Only members with @Members OR @Subscribers role will receive the DM.

---

# Quick Example: Send to Specific Users

## Send to specific individuals

Just ask the AI:
> "Send a message to @Alice, @Bob, and @Charlie asking them to confirm attendance"

The AI will:
1. Create a campaign with target_type='users'
2. Extract user IDs from mentions
3. Send only to those users

## Manual Commands

### 1. Create campaign
```
/campaign create target:users
```

### 2. Set which users to target
```
/campaign set_targets campaign_id:2 users:@Alice,@Bob,@Charlie
```

Or use user IDs:
```
/campaign set_targets campaign_id:2 users:111111111,222222222,333333333
```

### 3. Preview and send
```
/campaign preview campaign_id:2
/campaign send campaign_id:2
```

Only Alice, Bob, and Charlie will receive the DM.

---

# Use Cases

## Moderator Announcements
```
target: roles
roles: @Moderator,@Admin
message: "Team meeting in 30 minutes!"
```

## VIP Exclusive Offers
```
target: roles
roles: @VIP,@Premium
message: "Early access to new features!"
```

## Direct Communication
```
target: users
users: @TeamLead,@ProjectManager
message: "Please review the proposal"
```

## All Members
```
target: dm
message: "Server update announcement"
```
