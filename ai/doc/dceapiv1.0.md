1.	全局公共参数
请求Header参数
参数名	示例值	参数类型	是否必填	参数描述
apikey	-	string	是	apikey无需加密
Authorization	Bearer 【token值】	string	是	token值，固定以Bearer+英文空格开头，除登录接口外均需要

全局参数说明
参数名	示例值	参数类型	是否必填	参数描述
lang	zh	string	是	语言类型：“zh“代表中文，“en”代表英文
tradeType	1	number	是	交易类型：1期货，2期权
2.	状态码说明
状态码	说明
200	代表成功状态
500	代表内部错误，需查看具体错误信息
501	代表访问过于频繁，需降低访问频次
400	代表参数错误，请检查参数是否正确
401	代表该接口访问无权限，请检查接口是否正确
402	代表token过期，请重新获取 token
注：在客户端申请或重置的apikey与apisecret，会在1分钟内生效。
3.	登录
3.1.	登录

接口URL
http://www.dce.com.cn/dceapi/cms/auth/accessToken
请求方式
POST
请求Header参数
参数名	示例值	参数类型	是否必填	参数描述
apikey	-	string	是	申请的apikey
请求Body参数
{"secret": "申请的secret值"}
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "安全Token签发成功",
    "requestId": "94a3b611-30e3-48d6-ba52-010f93a35528",
    "data": {
        "tokenType": "Bearer",
        "token": "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJpbnRlcm5hbC1zZXJ2aWNlcyIsImNyZWF0ZWRfdGltZSI6MTc2MDAwNTU1NDAzNCwic2VydmljZV9uYW1lIjoib3JkZXItc2VydmljZSIsImlzcyI6ImFwaS1hdXRoLXNlcnZpY2UiLCJzdWIiOiJvcmRlci1zZXJ2aWNlIiwiaWF0IjoxNzYwMDA1NTU0LCJleHAiOjE3NjAwMDkxNTR9.riL05bZUQmmAq4v9eHahui5h5B5URaYcHNPJem-0pPI",
        "expiresIn": 3600
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求返回的状态码，常见如200表示成功。
msg	安全Token签发成功	string	用于返回关于API操作的具体消息，告知用户操作情况。
requestId	94a3b611-30e3-48d6-ba52-010f93a35528	string	唯一标识此次API请求，方便追踪和排查问题。
data	{}	object	存放API返回的具体数据内容，格式依业务而定。
data.tokenType	Bearer	string	表示token的类型，如Bearer类型用于认证。
data.token	eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJpbnRlcm5hbC1zZXJ2aWNlcyIsImNyZWF0ZWRfdGltZSI6MTc2MDAwNTU1NDAzNCwic2VydmljZV9uYW1lIjoib3JkZXItc2VydmljZSIsImlzcyI6ImFwaS1hdXRoLXNlcnZpY2UiLCJzdWIiOiJvcmRlci1zZXJ2aWNlIiwiaWF0IjoxNzYwMDA1NTU0LCJleHAiOjE3NjAwMDkxNTR9.riL05bZUQmmAq4v9eHahui5h5B5URaYcHNPJem-0pPI	string	用于认证和授权的令牌，包含用户相关信息。
data.expiresIn	3600	number	表示token的过期时间，单位通常为秒。
4.	资讯

4.1.	业务公告与通知

接口URL
http://www.dce.com.cn/dceapi/cms/info/articleByPage
请求方式
POST
请求Body参数
{
"columnId":"244",
"pageNo":1,
"siteId":5,
"pageSize":10
}
响应示例
•	成功(200)

{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1bd15517-74f1-4196-b974-e5bbfea0c789",
    "data": {
        "columnId": "244",
        "status": "0",
        "statusInfo": "",
        "resultList": [    
            {
                "id": "892228743449405276",
                "version": "1",
                "title": "测试新增文章同步",
                "subTitle": "",
                "infoSummary": "测试新增文章同步的正文",
                "sourceId": "",
                "showDate": "2025-09-24 17:40:36",
                "releaseDate": "2025-09-24 15:39:51",
                "content": "<p>测试新增文章同步的正文</p>",
                "keywords": "测试 新增 文章 同步 ",
                "entityType": "HTML",
                "titleImageUrl": "",
                "articleStaticUrl": "content/2025/ywggytz/892228743449405276.html",
                "articleDynamicUrl": "",
                "pageName": "业务公告与通知",
                "createDate": "2025-09-24 17:40:36"
            }
        ],
        "totalCount": 2183
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true代表成功，false代表。
code	200	number	表示API请求返回的状态码，200代表成功，不同状态码有不同含义。
msg	操作成功	string	对API操作结果的简要文字描述。
requestId	1bd15517-74f1-4196-b974-e5bbfea0c789	string	唯一标识此次API请求的ID，方便追踪和排查问题。
data	{}	object	-
data.columnId	244	string	资讯栏目ID
data.resultList	[]	array	存放API返回结果的列表，列表内每个元素为一条具体。
资讯			
data.resultList.version	1	string	该条资讯更新版本
data.resultList.title	测试新增文章同步	string	标题
data.resultList.subTitle	测试副标题	string	副标题
data.resultList.infoSummary	测试新增文章同步的正文	string	摘要
data.resultList.showDate	2025-09-24 17:40:36	string	展示
data.resultList.releaseDate	2025-09-24 15:39:51	string	发布时间
data.resultList.content	<p>测试新增文章同步的正文</p>	string	正文
data.resultList.keywords	测试 新增 文章 同步	string	关键字
data.resultList.entityType	HTML	string	标识结果项数据的实体类型，如HTML、JSON等。
data.resultList.titleImageUrl	http://example.com/image.jpg	string	结果项标题对应的图片链接，用于展示相关图片。
data.resultList.articleStaticUrl	content/2025/ywggytz/892228743449405276.html	string	文章的静态访问链接，用于获取静态内容。
data.resultList.articleDynamicUrl	http://example.com/article/892228743449405276	string	文章的动态访问链接，可进行动态交互。
data.resultList.pageName	业务公告与通知	string	结果项所属页面的名称，用于定位页面。
data.resultList.createDate	2025-09-24 17:40:36	string	结果项的创建日期时间，记录数据创建时间。
data.totalCount	2183	number	代表结果列表中数据项的总数量。

4.2.	活动公告与通知

接口URL
http://www.dce.com.cn/dceapi/cms/info/articleByPage
请求方式
POST
请求Body参数
{
"columnId":"245",
"pageNo":1,
"siteId":5,
"pageSize":10
}
响应示例
•	成功(200)

{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1bd15517-74f1-4196-b974-e5bbfea0c789",
    "data": {
        "columnId": "244",
        "status": "0",
        "statusInfo": "",
        "resultList": [    
            {
                "id": "892228743449405276",
                "version": "1",
                "title": "测试新增文章同步",
                "subTitle": "",
                "infoSummary": "测试新增文章同步的正文",
                "sourceId": "",
                "showDate": "2025-09-24 17:40:36",
                "releaseDate": "2025-09-24 15:39:51",
                "content": "<p>测试新增文章同步的正文</p>",
                "keywords": "测试 新增 文章 同步 ",
                "entityType": "HTML",
                "titleImageUrl": "",
                "articleStaticUrl": "content/2025/ywggytz/892228743449405276.html",
                "articleDynamicUrl": "",
                "pageName": "业务公告与通知",
                "createDate": "2025-09-24 17:40:36"
            }
        ],
        "totalCount": 2183
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true代表成功，false代表。
code	200	number	表示API请求返回的状态码，200代表成功，不同状态码有不同含义。
msg	操作成功	string	对API操作结果的简要文字描述。
requestId	1bd15517-74f1-4196-b974-e5bbfea0c789	string	唯一标识此次API请求的ID，方便追踪和排查问题。
data	{}	object	-
data.columnId	244	string	资讯栏目ID
data.resultList	[]	array	存放API返回结果的列表，列表内每个元素为一条具体。
资讯			
data.resultList.version	1	string	该条资讯更新版本
data.resultList.title	测试新增文章同步	string	标题
data.resultList.subTitle	测试副标题	string	副标题
data.resultList.infoSummary	测试新增文章同步的正文	string	摘要
data.resultList.showDate	2025-09-24 17:40:36	string	展示
data.resultList.releaseDate	2025-09-24 15:39:51	string	发布时间
data.resultList.content	<p>测试新增文章同步的正文</p>	string	正文
data.resultList.keywords	测试 新增 文章 同步	string	关键字
data.resultList.entityType	HTML	string	标识结果项数据的实体类型，如HTML、JSON等。
data.resultList.titleImageUrl	http://example.com/image.jpg	string	结果项标题对应的图片链接，用于展示相关图片。
data.resultList.articleStaticUrl	content/2025/ywggytz/892228743449405276.html	string	文章的静态访问链接，用于获取静态内容。
data.resultList.articleDynamicUrl	http://example.com/article/892228743449405276	string	文章的动态访问链接，可进行动态交互。
data.resultList.pageName	业务公告与通知	string	结果项所属页面的名称，用于定位页面。
data.resultList.createDate	2025-09-24 17:40:36	string	结果项的创建日期时间，记录数据创建时间。
data.totalCount	2183	number	代表结果列表中数据项的总数量。

4.3.	今日提示

接口URL
http://www.dce.com.cn/dceapi/cms/info/articleByPage
请求方式
POST
请求Body参数
{
"columnId":"1076",
"pageNo":1,
"siteId":5,
"pageSize":10
}
响应示例
•	成功(200)

{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1bd15517-74f1-4196-b974-e5bbfea0c789",
    "data": {
        "columnId": "244",
        "status": "0",
        "statusInfo": "",
        "resultList": [    
            {
                "id": "892228743449405276",
                "version": "1",
                "title": "测试新增文章同步",
                "subTitle": "",
                "infoSummary": "测试新增文章同步的正文",
                "sourceId": "",
                "showDate": "2025-09-24 17:40:36",
                "releaseDate": "2025-09-24 15:39:51",
                "content": "<p>测试新增文章同步的正文</p>",
                "keywords": "测试 新增 文章 同步 ",
                "entityType": "HTML",
                "titleImageUrl": "",
                "articleStaticUrl": "content/2025/ywggytz/892228743449405276.html",
                "articleDynamicUrl": "",
                "pageName": "业务公告与通知",
                "createDate": "2025-09-24 17:40:36"
            }
        ],
        "totalCount": 2183
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true代表成功，false代表。
code	200	number	表示API请求返回的状态码，200代表成功，不同状态码有不同含义。
msg	操作成功	string	对API操作结果的简要文字描述。
requestId	1bd15517-74f1-4196-b974-e5bbfea0c789	string	唯一标识此次API请求的ID，方便追踪和排查问题。
data	{}	object	-
data.columnId	244	string	资讯栏目ID
data.resultList	[]	array	存放API返回结果的列表，列表内每个元素为一条具体。
资讯			
data.resultList.version	1	string	该条资讯更新版本
data.resultList.title	测试新增文章同步	string	标题
data.resultList.subTitle	测试副标题	string	副标题
data.resultList.infoSummary	测试新增文章同步的正文	string	摘要
data.resultList.showDate	2025-09-24 17:40:36	string	展示
data.resultList.releaseDate	2025-09-24 15:39:51	string	发布时间
data.resultList.content	<p>测试新增文章同步的正文</p>	string	正文
data.resultList.keywords	测试 新增 文章 同步	string	关键字
data.resultList.entityType	HTML	string	标识结果项数据的实体类型，如HTML、JSON等。
data.resultList.titleImageUrl	http://example.com/image.jpg	string	结果项标题对应的图片链接，用于展示相关图片。
data.resultList.articleStaticUrl	content/2025/ywggytz/892228743449405276.html	string	文章的静态访问链接，用于获取静态内容。
data.resultList.articleDynamicUrl	http://example.com/article/892228743449405276	string	文章的动态访问链接，可进行动态交互。
data.resultList.pageName	业务公告与通知	string	结果项所属页面的名称，用于定位页面。
data.resultList.createDate	2025-09-24 17:40:36	string	结果项的创建日期时间，记录数据创建时间。
data.totalCount	2183	number	代表结果列表中数据项的总数量。
请求Header参数
参数名	示例值	参数类型	是否必填	参数描述
apikey	-	string	是	申请的apikey

4.4.	交易所新闻-文媒

接口URL
http://www.dce.com.cn/dceapi/cms/info/articleByPage
请求方式
POST
请求Body参数
{
"columnId":"246",
"pageNo":1,
"siteId":5,
"pageSize":10
}
响应示例
•	成功(200)

{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1bd15517-74f1-4196-b974-e5bbfea0c789",
    "data": {
        "columnId": "244",
        "status": "0",
        "statusInfo": "",
        "resultList": [    
            {
                "id": "892228743449405276",
                "version": "1",
                "title": "测试新增文章同步",
                "subTitle": "",
                "infoSummary": "测试新增文章同步的正文",
                "sourceId": "",
                "showDate": "2025-09-24 17:40:36",
                "releaseDate": "2025-09-24 15:39:51",
                "content": "<p>测试新增文章同步的正文</p>",
                "keywords": "测试 新增 文章 同步 ",
                "entityType": "HTML",
                "titleImageUrl": "",
                "articleStaticUrl": "content/2025/ywggytz/892228743449405276.html",
                "articleDynamicUrl": "",
                "pageName": "业务公告与通知",
                "createDate": "2025-09-24 17:40:36"
            }
        ],
        "totalCount": 2183
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true代表成功，false代表。
code	200	number	表示API请求返回的状态码，200代表成功，不同状态码有不同含义。
msg	操作成功	string	对API操作结果的简要文字描述。
requestId	1bd15517-74f1-4196-b974-e5bbfea0c789	string	唯一标识此次API请求的ID，方便追踪和排查问题。
data	{}	object	-
data.columnId	244	string	资讯栏目ID
data.resultList	[]	array	存放API返回结果的列表，列表内每个元素为一条具体。
资讯			
data.resultList.version	1	string	该条资讯更新版本
data.resultList.title	测试新增文章同步	string	标题
data.resultList.subTitle	测试副标题	string	副标题
data.resultList.infoSummary	测试新增文章同步的正文	string	摘要
data.resultList.showDate	2025-09-24 17:40:36	string	展示
data.resultList.releaseDate	2025-09-24 15:39:51	string	发布时间
data.resultList.content	<p>测试新增文章同步的正文</p>	string	正文
data.resultList.keywords	测试 新增 文章 同步	string	关键字
data.resultList.entityType	HTML	string	标识结果项数据的实体类型，如HTML、JSON等。
data.resultList.titleImageUrl	http://example.com/image.jpg	string	结果项标题对应的图片链接，用于展示相关图片。
data.resultList.articleStaticUrl	content/2025/ywggytz/892228743449405276.html	string	文章的静态访问链接，用于获取静态内容。
data.resultList.articleDynamicUrl	http://example.com/article/892228743449405276	string	文章的动态访问链接，可进行动态交互。
data.resultList.pageName	业务公告与通知	string	结果项所属页面的名称，用于定位页面。
data.resultList.createDate	2025-09-24 17:40:36	string	结果项的创建日期时间，记录数据创建时间。
data.totalCount	2183	number	代表结果列表中数据项的总数量。

4.5.	媒体看大商所-文媒

接口URL
http://www.dce.com.cn/dceapi/cms/info/articleByPage
请求方式
POST
请求Body参数
{
"columnId":"248",
"pageNo":1,
"siteId":5,
"pageSize":10
}
响应示例
•	成功(200)

{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1bd15517-74f1-4196-b974-e5bbfea0c789",
    "data": {
        "columnId": "244",
        "status": "0",
        "statusInfo": "",
        "resultList": [    
            {
                "id": "892228743449405276",
                "version": "1",
                "title": "测试新增文章同步",
                "subTitle": "",
                "infoSummary": "测试新增文章同步的正文",
                "sourceId": "",
                "showDate": "2025-09-24 17:40:36",
                "releaseDate": "2025-09-24 15:39:51",
                "content": "<p>测试新增文章同步的正文</p>",
                "keywords": "测试 新增 文章 同步 ",
                "entityType": "HTML",
                "titleImageUrl": "",
                "articleStaticUrl": "content/2025/ywggytz/892228743449405276.html",
                "articleDynamicUrl": "",
                "pageName": "业务公告与通知",
                "createDate": "2025-09-24 17:40:36"
            }
        ],
        "totalCount": 2183
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true代表成功，false代表。
code	200	number	表示API请求返回的状态码，200代表成功，不同状态码有不同含义。
msg	操作成功	string	对API操作结果的简要文字描述。
requestId	1bd15517-74f1-4196-b974-e5bbfea0c789	string	唯一标识此次API请求的ID，方便追踪和排查问题。
data	{}	object	-
data.columnId	244	string	资讯栏目ID
data.resultList	[]	array	存放API返回结果的列表，列表内每个元素为一条具体。
资讯			
data.resultList.version	1	string	该条资讯更新版本
data.resultList.title	测试新增文章同步	string	标题
data.resultList.subTitle	测试副标题	string	副标题
data.resultList.infoSummary	测试新增文章同步的正文	string	摘要
data.resultList.showDate	2025-09-24 17:40:36	string	展示
data.resultList.releaseDate	2025-09-24 15:39:51	string	发布时间
data.resultList.content	<p>测试新增文章同步的正文</p>	string	正文
data.resultList.keywords	测试 新增 文章 同步	string	关键字
data.resultList.entityType	HTML	string	标识结果项数据的实体类型，如HTML、JSON等。
data.resultList.titleImageUrl	http://example.com/image.jpg	string	结果项标题对应的图片链接，用于展示相关图片。
data.resultList.articleStaticUrl	content/2025/ywggytz/892228743449405276.html	string	文章的静态访问链接，用于获取静态内容。
data.resultList.articleDynamicUrl	http://example.com/article/892228743449405276	string	文章的动态访问链接，可进行动态交互。
data.resultList.pageName	业务公告与通知	string	结果项所属页面的名称，用于定位页面。
data.resultList.createDate	2025-09-24 17:40:36	string	结果项的创建日期时间，记录数据创建时间。
data.totalCount	2183	number	代表结果列表中数据项的总数量。

4.6.	新闻发布

接口URL
http://www.dce.com.cn/dceapi/cms/info/articleByPage
请求方式
POST
请求Body参数
{
"columnId":"242",
"pageNo":1,
"siteId":5,
"pageSize":10
}
响应示例
•	成功(200)

{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1bd15517-74f1-4196-b974-e5bbfea0c789",
    "data": {
        "columnId": "244",
        "status": "0",
        "statusInfo": "",
        "resultList": [    
            {
                "id": "892228743449405276",
                "version": "1",
                "title": "测试新增文章同步",
                "subTitle": "",
                "infoSummary": "测试新增文章同步的正文",
                "sourceId": "",
                "showDate": "2025-09-24 17:40:36",
                "releaseDate": "2025-09-24 15:39:51",
                "content": "<p>测试新增文章同步的正文</p>",
                "keywords": "测试 新增 文章 同步 ",
                "entityType": "HTML",
                "titleImageUrl": "",
                "articleStaticUrl": "content/2025/ywggytz/892228743449405276.html",
                "articleDynamicUrl": "",
                "pageName": "业务公告与通知",
                "createDate": "2025-09-24 17:40:36"
            }
        ],
        "totalCount": 2183
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true代表成功，false代表。
code	200	number	表示API请求返回的状态码，200代表成功，不同状态码有不同含义。
msg	操作成功	string	对API操作结果的简要文字描述。
requestId	1bd15517-74f1-4196-b974-e5bbfea0c789	string	唯一标识此次API请求的ID，方便追踪和排查问题。
data	{}	object	-
data.columnId	244	string	资讯栏目ID
data.resultList	[]	array	存放API返回结果的列表，列表内每个元素为一条具体。
资讯			
data.resultList.version	1	string	该条资讯更新版本
data.resultList.title	测试新增文章同步	string	标题
data.resultList.subTitle	测试副标题	string	副标题
data.resultList.infoSummary	测试新增文章同步的正文	string	摘要
data.resultList.showDate	2025-09-24 17:40:36	string	展示
data.resultList.releaseDate	2025-09-24 15:39:51	string	发布时间
data.resultList.content	<p>测试新增文章同步的正文</p>	string	正文
data.resultList.keywords	测试 新增 文章 同步	string	关键字
data.resultList.entityType	HTML	string	标识结果项数据的实体类型，如HTML、JSON等。
data.resultList.titleImageUrl	http://example.com/image.jpg	string	结果项标题对应的图片链接，用于展示相关图片。
data.resultList.articleStaticUrl	content/2025/ywggytz/892228743449405276.html	string	文章的静态访问链接，用于获取静态内容。
data.resultList.articleDynamicUrl	http://example.com/article/892228743449405276	string	文章的动态访问链接，可进行动态交互。
data.resultList.pageName	业务公告与通知	string	结果项所属页面的名称，用于定位页面。
data.resultList.createDate	2025-09-24 17:40:36	string	结果项的创建日期时间，记录数据创建时间。
data.totalCount	2183	number	代表结果列表中数据项的总数量。

5.	数据


5.1.	通用数据接口

5.1.1.	当前交易日

接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/maxTradeDate
请求方式
GET
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "946789d1-2924-45c4-8710-0ad22b72e0da",
    "data": {
        "tradeDate": "20251010"
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求返回的状态码，常见如200表示成功。
msg	操作成功	string	用于返回关于API操作结果的简要描述信息。
requestId	946789d1-2924-45c4-8710-0ad22b72e0da	string	唯一标识此次API请求的ID，方便追踪和排查问题。
data	{}	object	-
data.tradeDate	20251010	string	交易日

5.1.2.	品种列表

接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/variety
请求方式
GET
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "06f6ce8b-914a-4f38-9f8e-e058f5fc9aec",
    "data": [
        {
            "varietyId": "a",
            "varietyName": "豆一",
            "varietyEnglishName": "No.1 Soybean",
            "pic": "/file/icons/a.png",
            "varietyType": "农业品",
            "quotType": null
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求返回的状态码，常见如200表示成功。
msg	操作成功	string	用于返回关于API操作结果的简要描述信息。
requestId	06f6ce8b-914a-4f38-9f8e-e058f5fc9aec	string	唯一标识此次API请求的ID，方便追踪和排查问题。
data	-	array	-
data.varietyId	a	string	品种代码
data.varietyName	豆一	string	品种名称
data.varietyEnglishName	No.1 Soybean	string	品种名称-英文
data.pic	/file/icons/a.png	string	该品种对应的图片路径
data.varietyType	农业品	string	品种所属的类型
data.quotType	-	Null	

5.2.	行情统计


5.2.1.	夜盘行情

接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/dailystat/tiNightQuotes
请求方式
POST
请求Body参数
{
    "variety": "a",
    "tradeType": "1",
    "tradeDate": "20250930"
}
参数名	示例值	参数类型	是否必填	参数描述
variety	a	string	是	品种ID，全部为all
tradeType	1	number	是	交易类型：1期货，2期权。如传入其他值，则默认为1期货。
tradeDate	20250930	string	是	交易日
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "eb502d30-1ca7-419d-8239-13007193b1b9",
    "data": [
        {
            "variety": "豆一",
            "varietyOrder": "a",
            "delivMonth": "a2511",
            "open": "3939",
            "high": "3943",
            "low": "3924",
            "lastClear": "3931",
            "lastPrice": "3926",
            "diff": "-5",
            "declarePrice": "3926/3929",
            "volumn": 34717,
            "openInterest": 154442,
            "diffI": -7358,
            "turnover": "136523.48",
            "varietyEn": "No.1 Soybeans",
            "turnoverEn": "1365234.81"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	eb502d30-1ca7-419d-8239-13007193b1b9	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.variety	豆一	string	品种名称
data.varietyOrder	a	string	品种id
data.delivMonth	a2511	string	合约
data.open	3939	string	开盘价
data.high	3943	string	最高价
data.low	3924	string	最低价
data.lastClear	3931	string	前结算价
data.lastPrice	3926	string	最新价
data.diff	-5	string	涨跌
data.declarePrice	3926/3929	string	买价/卖价
data.volumn	34717	number	成交量
data.openInterest	154442	number	持仓量
data.diffI	-7358	number	持仓量变化
data.turnover	136523.48	string	成交额
data.varietyEn	No.1 Soybeans	string	品种名称-英文
data.turnoverEn	1365234.81	string	成交额-英文

5.2.2.	日行情

接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/dailystat/dayQuotes
请求方式
POST
请求Body参数
{
    "varietyId": "all",
    "tradeDate": "20251014",
    "tradeType": "2",
    "lang": "zh",
    "statisticsType": 2
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	all	string	是	品种id，全部为all
tradeDate	20251014	string	是	交易日
tradeType	2	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
statisticsType	2	number	否	期权统计类型：0-合约，1-系列，2-品种
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "a717415b-6bc8-40b0-a338-61b0dfa8e541",
    "data": [
        {
            "variety": "豆一",
            "contractId": "a2511",
            "open": "3930",
            "high": "3984",
            "low": "3930",
            "close": "3975",
            "lastClear": "3929",
            "clearPrice": "3960",
            "diff": "46",
            "diff1": "31",
            "delta": null,
            "volumn": 105525,
            "openInterest": 137560,
            "diffI": 951,
            "turnover": "417896.18",
            "matchQtySum": 0,
            "diffT": null,
            "volumnRate": null,
            "openInterestRate": null,
            "periodOverPeriodChg": null,
            "diffV": null,
            "impliedVolatility": null,
            "seriesId": null
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	09e1f8f6-5beb-4861-a330-feb13dbb92ab	string	-
data	-	array	-
data.variety	豆一	string	品种名称
data.contractId	-	null	合约/交易代码
data.high	3943	string	最高价
data.low	3924	string	最低价
data.close	-	null	收盘价
data.lastClear	3931	string	前结算价
data.clearPrice	-	null	结算价
data.diff	-5	string	涨跌
data.diff1	-	null	涨跌1
data.delta	-	null	Delta
data.volumn	34717	number	成交量
data.openInterest	154442	number	持仓量
data.diffI	-7358	number	持仓量变化
data.turnover	136523.48	string	成交额
data.matchQtySum	0	number	行权量
data.diffT	-	null	成交额变化
data.volumnRate	-	null	期权期货成交比
data.openInterestRate	-	null	期权期货持仓比
data.periodOverPeriodChg	-	null	-
data.diffV	-	null	成交量变化
data.impliedVolatility	-	null	隐含波动率
data.seriesId	-	null	期权系列
data.open	-	null	开盘价

5.2.3.	周行情



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/dailystat/weekQuotes
请求方式
POST
请求Body参数
{
    "varietyId": "all",
    "tradeDate": "20251014",
    "tradeType": "2",
    "lang": "zh",
    "statisticsType": 1
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	all	string	是	品种id，全部为all
tradeDate	20251014	string	是	交易日
tradeType	2	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
statisticsType	1	number	否	期权统计类型：0-合约，1-系列，2-品种，当请求类型为期权时候必填。
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "ba8a9cfe-09b2-461d-9a54-9b189dff07d4",
    "data": [
        {
            "variety": "豆一",
            "varietyOrder": "a",
            "contractId": "a2207",
            "open": "6001",
            "high": "6001",
            "low": "5749",
            "close": "5844",
            "clearPrice": "5869",
            "diff": "-234",
            "volumn": 2650,
            "openInterest": 2254,
            "diffI": -3573,
            "turnover": "1.56",
            "matchQtySum": 0,
            "diffT": null,
            "volumnRate": null,
            "openInterestRate": null,
            "periodOverPeriodChg": null,
            "diffV": null,
            "impliedVolatility": null,
            "seriesId": null,
            "avgOpenInterest": 0,
            "yearTotalVolume": 0,
            "yearAvgOpenInterest": 0,
            "yearTurnover": null,
            "yearMatchQtySum": 0
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	ba8a9cfe-09b2-461d-9a54-9b189dff07d4	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.variety	豆一	string	品种名称
data.varietyOrder	a	string	品种id
data.contractId	a2207	string	合约/期权系列
data.open	6001	string	周开盘价
data.high	6001	string	最高价
data.low	5749	string	最低价
data.close	5844	string	周收盘价
data.clearPrice	5869	string	周末结算价/周结算价
data.diff	-234	string	涨跌
data.volumn	2650	number	成交量
data.openInterest	2254	number	持仓量/期末持仓量
data.diffI	-3573	number	持仓量变化
data.turnover	1.56	string	成交额
data.matchQtySum	0	number	行权量
data.diffT	-	null	成交额变化
data.volumnRate	-	null	期权期货成交比
data.openInterestRate	-	null	期权期货持仓比
data.periodOverPeriodChg	-	null	-
data.diffV	-	null	成交量变化
data.impliedVolatility	-	null	期末隐含波动率
data.seriesId	-	null	期权系列
data.avgOpenInterest	0	number	日均持仓量
data.yearTotalVolume	0	number	-
data.yearAvgOpenInterest	0	number	-
data.yearTurnover	-	null	-
data.yearMatchQtySum	0	number	-

5.2.4.	月行情



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/dailystat/monthQuotes
请求方式
POST
请求Body参数
{
    "variety": "b",
    "tradeDate": "20251014",
    "lang": "zh",
    "tradeType": "2",
    "statisticsType": 0
}
参数名	示例值	参数类型	是否必填	参数描述
variety	b	string	是	品种id，全部为all
tradeDate	20251014	string	是	交易日
lang	zh	string	是	固定值：zh代表中文，en代表英文
tradeType	2	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
statisticsType	0	number	否	期权统计类型：0-合约，1-系列，2-品种，当请求类型为期权时候必填。
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "81cbf3db-3725-4d42-bdb8-61bf50df87f0",
    "data": [
        {
            "variety": "豆一",
            "contractId": "a2511",
            "open": "3930",
            "high": "3988",
            "low": "3930",
            "close": "3953",
            "clearPrice": "3958",
            "diff": "24",
            "volumn": 215849,
            "openInterest": 125633,
            "diffI": -10976,
            "turnover": "85.47",
            "delivMonth": "a2511",
            "varietyOrder": "a",
            "matchQtySum": 0,
            "impliedVolatility": null,
            "diffV": 0,
            "diffT": null,
            "periodOverPeriodChg": null,
            "seriesId": null,
            "volumnRate": null,
            "openInterestRate": null,
            "avgOpenInterest": 0,
            "quoteKey": null
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	81cbf3db-3725-4d42-bdb8-61bf50df87f0	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.variety	豆一	string	品种名称
data.contractId	a2511	string	合约
data.open	3930	string	月开盘价
data.high	3988	string	最高价
data.low	3930	string	最低价
data.close	3953	string	月末收盘价/月收盘价
data.clearPrice	3958	string	月末结算价
data.diff	24	string	涨跌
data.volumn	215849	number	成交量
data.openInterest	125633	number	持仓量/期末持仓量
data.diffI	-10976	number	持仓量变化
data.turnover	85.47	string	成交额
data.delivMonth	a2511	string	合约
data.varietyOrder	a	string	品种id
data.matchQtySum	0	number	行权量
data.impliedVolatility	-	null	期末隐含波动率
data.diffV	0	number	成交量变化
data.diffT	-	null	成交额变化
data.periodOverPeriodChg	-	null	-
data.seriesId	-	null	期权系列
data.volumnRate	-	null	期权期货成交比
data.openInterestRate	-	null	期权期货持仓比
data.avgOpenInterest	0	number	日均持仓量
data.quoteKey	-	null	-

5.2.5.	合约最值统计-成交量



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/phasestat/contractMonthMax
请求方式
POST
请求Body参数
{
    "startMonth": "202510",
    "endMonth": "202510",
    "statContent": "0",
    "tradeType": "2",
    "lang": "zh"
}
参数名	示例值	参数类型	是否必填	参数描述
startMonth	202510	string	是	开始月份
endMonth	202510	string	是	结束月份
statContent	0	string	是	固定值：0成交量统计，1成交额统计，2持仓量统计，3价格统计
tradeType	2	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "9b34d32a-4b0c-4dce-907e-ead973c4d9b3",
    "data": [
        {
            "contractId": "a2511-C-3400",
            "sumAmount": 0,
            "maxAmount": 0,
            "maxAmountDate": "20251009",
            "minAmount": 0,
            "minAmountDate": "20251009",
            "avgAmount": 0
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	9b34d32a-4b0c-4dce-907e-ead973c4d9b3	string	-
data	-	array	-
data.contractId	a2511-C-3400	string	合约
data.sumAmount	0	number	总成交量
data.maxAmount	0	number	最大成交量
data.maxAmountDate	20251009	string	出现日期-最大成交量
data.minAmount	0	number	最小成交量
data.minAmountDate	20251009	string	出现日期-最小成交量
data.avgAmount	0	number	日均成交量

5.2.6.	合约最值统计-成交额



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/phasestat/contractMonthMax
请求方式
POST
请求Body参数
{
    "startMonth": "202510",
    "endMonth": "202510",
    "statContent": "1",
    "tradeType": "2",
    "lang": "zh"
}
参数名	示例值	参数类型	是否必填	参数描述
startMonth	202510	string	是	开始月份
endMonth	202510	string	是	结束月份
statContent	1	string	是	固定值：0成交量统计，1成交额统计，2持仓量统计，3价格统计
tradeType	2	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "f2bdf85f-eeb5-4977-9234-1d4611b34a94",
    "data": [
        {
            "contractId": "a2511-C-3400",
            "sumTurnover": "0",
            "maxTurnover": "0",
            "maxTurnoverDate": "20251009",
            "minTurnover": "0",
            "minTurnoverDate": "20251009",
            "avgTurnover": "0"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	f2bdf85f-eeb5-4977-9234-1d4611b34a94	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.contractId	a2511-C-3400	string	合约
data.sumTurnover	0	string	总成交额
data.maxTurnover	0	string	最大成交额
data.maxTurnoverDate	20251009	string	出现日期-最大成交额
data.minTurnover	0	string	最小成交额
data.minTurnoverDate	20251009	string	出现日期-最小成交额
data.avgTurnover	0	string	日均成交量

5.2.7.	合约最值统计-持仓量



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/phasestat/contractMonthMax
请求方式
POST
请求Body参数
{
    "startMonth": "202510",
    "endMonth": "202510",
    "statContent": "2",
    "tradeType": "2",
    "lang": "zh"
}
参数名	示例值	参数类型	是否必填	参数描述
startMonth	202510	string	是	开始月份
endMonth	202510	string	是	结束月份
statContent	2	string	是	固定值：0成交量统计，1成交额统计，2持仓量统计，3价格统计
tradeType	2	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1c079764-655a-4fc4-ab93-a0dc9e0c9e77",
    "data": [
        {
            "contractId": "a2511-C-3400",
            "sumOpeni": 0,
            "maxOpeni": 0,
            "maxOpeniDate": "20251009",
            "minOpeni": 0,
            "minOpeniDate": "20251009",
            "avgOpeni": 0
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	1c079764-655a-4fc4-ab93-a0dc9e0c9e77	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.contractId	a2511-C-3400	string	合约
data.sumOpeni	0	number	总持仓量
data.maxOpeni	0	number	最大持仓量
data.maxOpeniDate	20251009	string	出现日期-最大持仓量
data.minOpeni	0	number	最小持仓量
data.minOpeniDate	20251009	string	出现日期-最小持仓量
data.avgOpeni	0	number	日均持仓量

5.2.8.	合约最值统计-价格统计

接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/phasestat/contractMonthMax
请求方式
POST
请求Body参数
{
    "startMonth": "202510",
    "endMonth": "202510",
    "statContent": "3",
    "tradeType": "2",
    "lang": "zh"
}
参数名	示例值	参数类型	是否必填	参数描述
startMonth	202510	string	是	开始月份
endMonth	202510	string	是	结束月份
statContent	3	string	是	固定值：0成交量统计，1成交额统计，2持仓量统计，3价格统计
tradeType	2	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "cde65c9b-fe61-47a6-917a-0e9bf8739789",
    "data": [
        {
            "contractId": "a2511-C-3400",
            "open": "0",
            "close": "558",
            "high": "0",
            "highDate": "20251009",
            "low": "0",
            "lowDate": "20251009",
            "clearPrice": "558"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	cde65c9b-fe61-47a6-917a-0e9bf8739789	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.contractId	a2511-C-3400	string	合约
data.open	0	string	期初开盘价
data.close	558	string	期末收盘价
data.high	0	string	最高价
data.highDate	20251009	string	出现日期-最高价
data.low	0	string	最低价
data.lowDate	20251009	string	出现日期-最低价
data.clearPrice	558	string	期末结算价

5.2.9.	品种月度统计



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/phasestat/varietyMonthYearStat
请求方式
POST
请求Body参数
{
    "tradeMonth": "202509",
    "tradeType": "1",
    "lang": "zh"
}
参数名	示例值	参数类型	是否必填	参数描述
tradeMonth	202509	string	是	查询月份
tradeType	1	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "b4ac5692-d937-4c4b-a030-9c1e9ef67a0b",
    "data": [
        {
            "variety": "豆一",
            "thisMonthVolumn": 3325059,
            "volumnBalance": "52.53",
            "volumnChain": "-8.03",
            "thisYearVolumn": 37254003,
            "yearVolumnChain": "81.52",
            "thisMonthTurnover": "1307.3485909",
            "turnoverBalance": "41.63",
            "turnoverChain": "-10.8",
            "thisYearTurnover": "15239.8051138",
            "yearTurnoverChain": "61.81",
            "thisMonthOpeni": 316993,
            "openiBalance": "54.08",
            "openiChain": "-15.54"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	b4ac5692-d937-4c4b-a030-9c1e9ef67a0b	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.variety	豆一	string	品种名称
data.thisMonthVolumn	3325059	number	本月成交量
data.volumnBalance	52.53	string	本月成交量同比
data.volumnChain	-8.03	string	本月成交量环比
data.thisYearVolumn	37254003	number	本年成交量
data.yearVolumnChain	81.52	string	本年成交量同比
data.thisMonthTurnover	1307.3485909	string	本月成交额
data.turnoverBalance	41.63	string	本月成交额同比
data.turnoverChain	-10.8	string	本月成交额环比
data.thisYearTurnover	15239.8051138	string	本年成交额
data.yearTurnoverChain	61.81	string	本年成交额同比
data.thisMonthOpeni	316993	number	月末持仓
data.openiBalance	54.08	string	持仓量同比
data.openiChain	-15.54	string	持仓量环比

5.2.10.	合约停板查询
接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/phasestat/riseFallEvent
请求方式
POST
请求Body参数
{
    "startDate": "20251009",
    "endDate": "20251009",
    "varietyId": "all",
    "lang": "zh"
}
参数名	示例值	参数类型	是否必填	参数描述
startDate	20251009	string	是	开始月份
endDate	20251009	string	是	结束月份
varietyId	all	string	是	品种id，全部为all
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "26dcd15f-14ce-4711-95fc-8031c591bbcd",
    "data": [
        {
            "tradeDate": "20240930",
            "contractId": "jm2411",
            "direction": "涨停",
            "times": 1
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	26dcd15f-14ce-4711-95fc-8031c591bbcd	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.tradeDate	20240930	string	日期
data.contractId	jm2411	string	合约
data.direction	涨停	string	停板
data.times	1	number	个数

5.2.11.	分时结算参考价



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/dailystat/divisionPriceInfo
请求方式
POST
请求Body参数
{
    "varietyId": "a",
    "tradeDate": "20251009",
    "tradeType": "1"
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
tradeDate	20251009	string	是	交易日
tradeType	1	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1b8511ac-bd71-4e60-8fac-02d03dddc342",
    "data": [
        {
            "calculateDate": "20251009",
            "calculateTime": "14:30",
            "varietyName": "豆一",
            "varietyEnName": "No.1 Soybeans",
            "contractId": "a2511",
            "clearPrice": 3958,
            "seriesId": null,
            "volatility": 0
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	1b8511ac-bd71-4e60-8fac-02d03dddc342	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.calculateDate	20251009	string	交易日期
data.calculateTime	14:30	string	计算时间
data.varietyName	豆一	string	品种名称
data.varietyEnName	No.1 Soybeans	string	品种名称-英文
data.contractId	a2511	string	合约
data.clearPrice	3958	number	结算参考价
data.seriesId	-	null	合约
data.volatility	0	number	结算参考隐含波动率

5.3.	交割统计

5.3.1.	交割数据



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/deliverystat/delivery
请求方式
POST
请求Body参数
{
    "varietyId": "a",
    "startMonth": "202501",
"varietyType": "1",
    "endMonth": "202510"
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
startMonth	202501	string	是	开始月份
endMonth	202510	string	是	结束月份
varietyType	1	string	是	0,实物交割数据;1,月均价交割数据
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "5680b88f-4eac-4f27-97e3-3c8b8b4daf99",
    "data": [
        {
            "variety": "豆一",
            "varietyEn": "No.1 Soybeans",
            "contractId": "a2501",
            "deliveryDate": "20250106",
            "deliveryQty": 2397,
            "deliveryAmt": "91473930"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	对API操作结果的简要文字描述。
requestId	5680b88f-4eac-4f27-97e3-3c8b8b4daf99	string	用于唯一标识一次API请求，方便追踪和排查问题。
data	{}	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.variety	豆一	string	品种名称
data.varietyEn	No.1 Soybeans	string	品种名称-英文
data.contractId	-	null	合约
data.deliveryDate	20250106	string	交割日期
data.deliveryQty	2397	number	交割量
data.deliveryAmt	91473930	string	交割金额

5.3.2.	交割配对表



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/deliverystat/deliveryMatch
请求方式
POST
请求Body参数
{
    "varietyId": "b",
    "contractId": "all",
    "startMonth": "202510",
    "endMonth": "202510"
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	b	string	是	品种id
contractId	all	string	是	合约id
startMonth	202510	string	是	开始月份
endMonth	202510	string	是	结束月份
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "983cfa85-d719-46c1-8ba8-36e2ecee0965",
    "data": [
        {
            "contractId": "b2510",
            "matchDate": "20251009",
            "buyMemberId": "0080",
            "deliveryQty": 100,
            "sellMemberId": "0125",
            "deliveryPrice": "3648"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	983cfa85-d719-46c1-8ba8-36e2ecee0965	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.contractId	b2510	string	合约
data.matchDate	20251009	string	配对日期
data.buyMemberId	0080	string	买会员号
data.deliveryQty	100	number	配对手数
data.sellMemberId	0125	string	卖会员号
data.deliveryPrice	3648	string	交割结算价

5.3.3.	仓单日报



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/dailystat/wbillWeeklyQuotes
请求方式
POST
请求Body参数
{
    "varietyId": "a",
    "tradeDate": "20251009"
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
tradeDate	20251009	string	是	交易日
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "6964b389-cad5-4751-a6ea-9183f70db658",
    "data": {
        "entityList": [
            {
                "varietyOrder": "a",
                "groupCodeOrder": null,
                "whCodeOrder": "_160",
                "whType": "2",
                "variety": "豆一",
                "genDate": "20251009",
                "whAbbr": "哈尔滨益海",
                "deliveryAbbr": null,
                "lastWbillQty": 2200,
                "regWbillQty": null,
                "logoutWbillQty": null,
                "wbillQty": 2200,
                "diff": 0
            }
        ],
        "ifAgioFlag": "0",
        "agioDeliType": null,
        "ifAgioBrandFlag": null
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	6964b389-cad5-4751-a6ea-9183f70db658	string	-
data	-	object	用于承载API返回的具体数据内容，通常为JSON格式。
data.entityList	-	array	-
data.entityList.varietyOrder	a	string	-
data.entityList.groupCodeOrder	-	null	-
data.entityList.whCodeOrder	_160	string	-
data.entityList.whType	2	string	-
data.entityList.variety	豆一	string	品种名称
data.entityList.genDate	20251009	string	-
data.entityList.whAbbr	哈尔滨益海	string	仓库/分库
data.entityList.deliveryAbbr	-	null	-
data.entityList.lastWbillQty	2200	number	昨日仓单量（手）
data.entityList.regWbillQty	-	null	-
data.entityList.logoutWbillQty	-	null	可选提货地点/分库-数量
data.entityList.wbillQty	2200	number	今日仓单量（手）
data.entityList.diff	0	number	增减（手）
data.ifAgioFlag	0	string	-
data.agioDeliType	-	null	-
data.ifAgioBrandFlag	-	null	-

5.3.4.	一次性交割卖方仓单查询



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/DeliveryStatistics/tcCongregateDeliveryQuotes
请求方式
POST
请求Body参数
{
    "variety": "all",
    "contractMonth": "202508"
}
参数名	示例值	参数类型	是否必填	参数描述
variety	a	string	是	品种id，全部为all
contractMonth	202510	string	是	查询月份
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "87085f70-d5bb-4f64-8cb4-f2e90c5ed7dd",
    "data": [
        {
            "varietyId": "b",
            "varietyName": "豆二",
            "contract": "b2508",
            "warehouseName": "东莞市富之源饲料蛋白开发有限公司",
            "wbillQuantity": "200",
            "agreeablePlace": null,
            "agreeableBrand": null,
            "agreeableQuality": null,
            "agreeableQuantity": null,
            "agreeableSpread": null,
            "contracts": null,
            "contractWay": null,
            "whGroupName": null
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	87085f70-d5bb-4f64-8cb4-f2e90c5ed7dd	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.varietyId	b	string	品种代码
data.varietyName	豆二	string	品种名称
data.contract	b2508	string	合约
data.warehouseName	东莞市富之源饲料蛋白开发有限公司	string	仓库/分库
data.wbillQuantity	200	string	仓单数量
data.agreeablePlace	-	null	可协议地点
data.agreeableBrand	-	null	可协议品牌
data.agreeableQuality	-	Null	可协议货物质量
data.agreeableQuantity	-	null	可协议数量（手）
data.agreeableSpread	-	null	协议价差（元/吨）
data.contracts	-	null	联系人
data.contractWay	-	null	联系方式
data.whGroupName	-	Null	集团名称

5.3.5.	滚动交割卖方交割意向表



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/DeliveryStatistics/rollDeliverySellerIntention
请求方式
POST
请求Body参数
{"variety":"all","date":"20251013"}
参数名	示例值	参数类型	是否必填	参数描述
variety	a	string	是	品种id，全部为all
date	20251009	string	是	查询日期
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "64f231f3-fc54-46fa-b2e3-f7c0ceb0f047",
    "data": [
        {
            "varietyId": "j",
            "varietyName": "焦炭",
            "contract": "j2510",
            "type": "仓库",
            "warehouseCode": "249",
            "warehouseName": "山西亚鑫能源集团有限公司（日照港）",
            "quantity": "40",
            "agreeablePlace": null,
            "agreeableBrand": null,
            "agreeableQuality": null,
            "agreeableQuantity": null,
            "agreeableSpread": null,
            "contracts": null,
            "contractWay": null,
            "tradeDate": "20251013",
            "whGroupName": null,
            "deliveryWay": "滚动交割"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	64f231f3-fc54-46fa-b2e3-f7c0ceb0f047	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.varietyId	j	string	品种代码
data.varietyName	焦炭	string	品种名称
data.contract	j2510	string	合约
data.type	仓库	string	仓库/车板
data.warehouseCode	249	string	-
data.warehouseName	山西亚鑫能源集团有限公司（日照港）	string	仓库名称
data.quantity	40	string	数量（手）
data.agreeablePlace	-	Null	可协议地点
data.agreeableBrand	-	null	可协议品牌
data.agreeableQuality	-	null	可协议货物质量
data.agreeableQuantity	-	null	可协议数量（手）
data.agreeableSpread	-	null	协议价差（元/吨）
data.contracts	-	null	联系人
data.contractWay	-	null	联系方式
data.tradeDate	20251013	string	交易
data.whGroupName	-	null	集团名称
data.deliveryWay	滚动交割	string	交割方式

5.3.6.	交割结算价



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/quotesdata/bondedDelivery
请求方式
POST
请求Body参数
{"startDate":"20201009","endDate":"20251009"}
参数名	示例值	参数类型	是否必填	参数描述
startDate	20251009	string	是	开始月份
endDate	20251009	string	是	结束月份
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "63d10ca3-c56d-4fa4-ac9f-fbc406f2ce12",
    "data": [
        {
            "deliveryDate": "20201013",
            "deliveryWay": "滚动交割",
            "varietyId": "苯乙烯",
            "contractId": "eb2010",
            "whAbbr": null,
            "bondedDeliveryPrice": null,
            "deliveryPrice": "5400"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	63d10ca3-c56d-4fa4-ac9f-fbc406f2ce12	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.deliveryDate	20201013	string	日期
data.deliveryWay	滚动交割	string	交割方式
data.varietyId	苯乙烯	string	品种名称
data.contractId	eb2010	string	合约
data.whAbbr	-	null	-
data.bondedDeliveryPrice	-	null	-
data.deliveryPrice	5400	string	结算价

5.3.7.	保税交割结算价



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/quotesdata/tdBondedDelivery
请求方式
POST
请求Body参数
{"startDate":"20171001","endDate":"20201009"}
参数名	示例值	参数类型	是否必填	参数描述
startDate	20251009	string	是	开始月份
endDate	20251009	string	是	结束月份
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "cf27886b-d8e5-43a7-8945-b3b905934b31",
    "data": [
        {
            "deliveryDate": "20190828",
            "deliveryWay": "期转现交割",
            "varietyId": "i-铁矿石",
            "contractId": "i1912",
            "whAbbr": "大连港(铁矿石保税)",
            "bondedDeliveryPrice": "617.5",
            "deliveryPrice": "699"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	cf27886b-d8e5-43a7-8945-b3b905934b31	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.deliveryDate	20190828	string	交割日期
data.deliveryWay	期转现交割	string	交割方式
data.varietyId	i-铁矿石	string	品种代码
data.contractId	i1912	string	合约
data.whAbbr	大连港(铁矿石保税)	string	仓库/分库
data.bondedDeliveryPrice	617.5	string	保税交割结算价
data.deliveryPrice	699	string	结算价

5.3.8.	纤维板厂库自报换货差价



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/quotesdata/queryFactorySpotAgioQuotes
请求方式
POST
请求Body参数
无
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "1b9fe8dc-9c7d-4ffd-be10-50f5da95729b",
    "data": [
        {
            "seqNo": "1",
            "whAbbr": "宿迁立华",
            "varietyId": "a",
            "varietyName": "豆一",
            "whCode": "506",
            "bh": null,
            "mdmin": null,
            "mdmax": null,
            "jq": null,
            "agio": null,
            "minExchangeAmount": null,
            "whAddr": null,
            "connectPerson": null,
            "tel": null
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	1b9fe8dc-9c7d-4ffd-be10-50f5da95729b	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.seqNo	1	string	-
data.whAbbr	宿迁立华	string	厂库简称
data.varietyId	a	string	品种代码
data.varietyName	豆一	string	品种名称
data.whCode	506	string	-
data.bh	-	null	厚度（mm）
data.mdmin	-	null	密度≥（g/cm3）
data.mdmax	-	null	密度≤（g/cm3）
data.jq	-	null	甲醛≤（mg/m3）
data.agio	-	null	换货差价（元/立方米）
data.minExchangeAmount	-	null	最低换货数量（立方米）
data.whAddr	-	null	地点
data.connectPerson	-	null	联系人
data.tel	-	null	联系方式

5.3.9.	仓库自报升贴水



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/deliverypara/floatingAgio
请求方式
POST
请求Body参数
{"varietyId":"all","tradeDate":"20251010"}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
tradeDate	20251010	string	是	交易日
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "d56f04ea-4d44-49bc-9099-c49b75359c8f",
    "data": {
        "entityList": [
            {
                "varietyId": "c",
                "varietyName": "玉米",
                "validDate": "20251010",
                "whCode": "555",
                "whName": "冀粮永安",
                "avgAgio": "40",
                "whGroupAbbr": "河北粮产",
                "brandAbbr": null
            }
        ],
        "ifAgioFlag": null,
        "agioDeliType": null,
        "ifAgioBrandFlag": null
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	d56f04ea-4d44-49bc-9099-c49b75359c8f	string	-
data	-	object	用于承载API返回的具体数据内容，通常为JSON格式。
data.entityList	-	array	-
data.entityList.varietyId	c	string	品种id
data.entityList.varietyName	玉米	string	品种名称
data.entityList.validDate	20251010	string	-
data.entityList.whCode	555	string	-
data.entityList.whName	冀粮永安	string	仓库名称(提货地点)
data.entityList.avgAgio	40	string	升贴水（元/吨）
data.entityList.whGroupAbbr	河北粮产	string	集团名称
data.entityList.brandAbbr	-	null	品牌
data.ifAgioFlag	-	null	-
data.agioDeliType	-	null	-
data.ifAgioBrandFlag	-	null	-

5.3.10.	胶合板交割商品查询



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/deliverystat/queryPlywoodDeliveryCommodity
请求方式
POST
请求Body参数
{}
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "ce2e9141-8bcc-40eb-885a-2af568c8c067",
    "data": [
        {
            "applyId": "7",
            "whName": "湖北福汉木业国际贸易有限公司",
            "whAbbr": "福汉木业",
            "uploadFileId": "a8398af19d8446c99c1b09b87c0eae86",
            "fileSize": 4948992,
            "uploadFileName": "湖北福汉木业国际贸易有限公司 厂库广西畔森- 花色.docx"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	ce2e9141-8bcc-40eb-885a-2af568c8c067	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.applyId	7	string	-
data.whName	湖北福汉木业国际贸易有限公司	string	厂库/车板场所
data.whAbbr	福汉木业	string	胶合板交割商品附件
data.uploadFileId	a8398af19d8446c99c1b09b87c0eae86	string	文件id
data.fileSize	4948992	number	文件大小
data.uploadFileName	湖北福汉木业国际贸易有限公司 厂库广西畔森- 花色.docx	string	文件名称

5.4.	会员成交持仓统计


5.4.1.	日成交持仓排名



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/dailystat/memberDealPosi
请求方式
POST
请求Body参数
{
    "varietyId": "a",
    "tradeDate": "20251010",
    "contractId": "a2601",
    "tradeType": "1"
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id
tradeDate	20251010	string	是	交易日
contractId	a2601	string	是	合约id
tradeType	1	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "131247d6-9a19-48e6-9761-19cfd08b72a8",
    "data": {
        "contractId": "期货公司会员",
        "todayQty": 87175,
        "qtySub": 8704,
        "todayBuyQty": 94967,
        "buySub": 1357,
        "todaySellQty": 121386,
        "sellSub": 2794,
        "qtyFutureList": [
            {
                "rank": "1",
                "qtyAbbr": "东证期货（代客）",
                "todayQty": 22979,
                "qtySub": 1973
            }
        ],
        "buyFutureList": [
            {
                "rank": "1",
                "buyAbbr": "永安期货（代客）",
                "todayBuyQty": 17012,
                "buySub": 2144
            }
        ],
        "sellFutureList": [
            {
                "rank": "1",
                "sellAbbr": "摩根大通（代客）",
                "todaySellQty": 31199,
                "sellSub": -1319
            }
        ]
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	131247d6-9a19-48e6-9761-19cfd08b72a8	string	-
data	-	object	用于承载API返回的具体数据内容，通常为JSON格式。
data.contractId	期货公司会员	string	合约
data.todayQty	87175	number	成交量-汇总
data.qtySub	8704	number	增减-汇总-成交量
data.todayBuyQty	94967	number	持买单量-汇总
data.buySub	1357	number	增减-汇总-持买单量
data.todaySellQty	121386	number	持卖单量-汇总
data.sellSub	2794	number	增减-汇总-持卖单量
data.qtyFutureList	-	array	-
data.qtyFutureList.rank	1	string	名次-成交量
data.qtyFutureList.qtyAbbr	东证期货（代客）	string	会员简称-成交量
data.qtyFutureList.todayQty	22979	number	成交量
data.qtyFutureList.qtySub	1973	number	增减-成交量
data.buyFutureList	-	array	-
data.buyFutureList.rank	1	string	名次-买单
data.buyFutureList.buyAbbr	永安期货（代客）	string	会员简称-买单
data.buyFutureList.todayBuyQty	17012	number	持买单量-买单
data.buyFutureList.buySub	2144	number	增减-买单
data.sellFutureList	-	array	-
data.sellFutureList.rank	1	string	名次-卖单
data.sellFutureList.sellAbbr	摩根大通（代客）	string	会员简称-卖单
data.sellFutureList.todaySellQty	31199	number	持单量-卖单
data.sellFutureList.sellSub	-1319	number	增减-卖单

5.4.2.	日成交持仓排名-期权



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/dailystat/memberDealPosi
请求方式
POST
请求Body参数
{
    "varietyId": "a",
    "tradeDate": "20251013",
    "contractId": "a2511",
    "tradeType": "2"
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id
tradeDate	20251009	string	是	交易日
contractId	b2511	string	是	合约id
tradeType	1	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "5e5f5ba1-174e-4b9f-9c61-1e1162230ae1",
    "data": {
        "qtyOptionUpList": [
            {
                "rank": "1",
                "qtyAbbr": "东证期货（代客）",
                "todayQty": 8046,
                "qtySub": 1526
            }
        ],
        "buyOptionUpList": [
            {
                "rank": "1",
                "buyAbbr": "中信建投（代客）",
                "todayBuyQty": 4480,
                "buySub": 602
            }
        ],
        "sellOptionUpList": [
            {
                "rank": "1",
                "sellAbbr": "东证期货（代客）",
                "todaySellQty": 7060,
                "sellSub": 697
            }
        ],
        "qtyOptionDownList": [
            {
                "rank": "1",
                "qtyAbbr": "光大期货（代客）",
                "todayQty": 5053,
                "qtySub": 1835
            }
        ],
        "buyOptionDownList": [
            {
                "rank": "1",
                "buyAbbr": "国投期货（代客）",
                "todayBuyQty": 4342,
                "buySub": -612
            }
        ],
        "sellOptionDownList": [
            {
                "rank": "1",
                "sellAbbr": "东证期货（代客）",
                "todaySellQty": 4183,
                "sellSub": 326
            }
        ]
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	用于表示API操作是否成功，true表示成功，false表示。
code	200	number	表示API请求的状态码，常见如200代表成功。
msg	操作成功	string	-
requestId	5e5f5ba1-174e-4b9f-9c61-1e1162230ae1	string	-
data	-	object	用于承载API返回的具体数据内容，通常为JSON格式。
data.qtyOptionUpList	-	array	-
data.qtyOptionUpList.rank	1	string	名次-看涨期权-成交量
data.qtyOptionUpList.qtyAbbr	东证期货（代客）	string	会员简称-看涨期权-成交量
data.qtyOptionUpList.todayQty	8046	number	成交量-看涨期权
data.qtyOptionUpList.qtySub	1526	number	增减-看涨期权-成交量
data.buyOptionUpList	-	array	-
data.buyOptionUpList.rank	1	string	名次-看涨期权-买单
data.buyOptionUpList.buyAbbr	中信建投（代客）	string	会员简称-看涨期权-买单
data.buyOptionUpList.todayBuyQty	4480	number	持买单量-看涨期权
data.buyOptionUpList.buySub	602	number	增减-看涨期权-买单
data.sellOptionUpList	-	array	-
data.sellOptionUpList.rank	1	string	名次-看涨期权-卖单
data.sellOptionUpList.sellAbbr	东证期货（代客）	string	会员简称-看涨期权-卖单
data.sellOptionUpList.todaySellQty	7060	number	持卖单量-看涨期权
data.sellOptionUpList.sellSub	697	number	增减-看涨期权-卖单
data.qtyOptionDownList	-	array	-
data.qtyOptionDownList.rank	1	string	名次-看跌期权-成交量
data.qtyOptionDownList.qtyAbbr	光大期货（代客）	string	会员简称-看跌期权-成交量
data.qtyOptionDownList.todayQty	5053	number	成交量-看跌期权
data.qtyOptionDownList.qtySub	1835	number	增减-看跌期权-成交量
data.buyOptionDownList	-	array	-
data.buyOptionDownList.rank	1	string	名次-看跌期权-买单
data.buyOptionDownList.buyAbbr	国投期货（代客）	string	会员简称-看跌期权-买单
data.buyOptionDownList.todayBuyQty	4342	number	持买单量-看跌期权
data.buyOptionDownList.buySub	-612	number	增减-看跌期权-买单
data.sellOptionDownList	-	array	-
data.sellOptionDownList.rank	1	string	名次-看跌期权-卖单
data.sellOptionDownList.sellAbbr	东证期货（代客）	string	会员简称-看跌期权-卖单
data.sellOptionDownList.todaySellQty	4183	number	持卖单量-看跌期权
data.sellOptionDownList.sellSub	326	number	增减-看跌期权-卖单

5.4.3.	阶段成交排名



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/phasestat/memberDealCh
请求方式
POST
请求Body参数
{
    "variety": "a",
    "startMonth": "202510",
    "endMonth": "202510",
    "tradeType": "1"
}
参数名	示例值	参数类型	是否必填	参数描述
variety	a	string	是	品种id，全部为all
startMonth	202510	string	是	开始月份
endMonth	202510	string	是	结束月份
tradeType	1	string	是	固定值：0、1期货，2期权
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "4bf3e085-71c9-4468-9170-9378c785866e",
    "data": [
        {
            "seq": "1",
            "memberId": "0184",
            "memberName": "东证期货（代客）",
            "amtMemberId": "0184",
            "amtMemberName": "东证期货（代客）",
            "monthQty": 138550,
            "qtyRatio": 19.85,
            "monthAmt": 54.8379107,
            "amtRatio": 19.85
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	4bf3e085-71c9-4468-9170-9378c785866e	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.seq	1	string	-
data.memberId	0184	string	会员id-成交量
data.memberName	东证期货（代客）	string	会员简称-成交量
data.amtMemberId	0184	string	会员号-成交额
data.amtMemberName	东证期货（代客）	string	会员简称-成交额
data.monthQty	138550	number	成交量（手）
data.qtyRatio	19.85	number	比重-成交量
data.monthAmt	54.8379107	number	成交额（亿元）
data.amtRatio	19.85	number	比重-成交额

5.5.	交易参数


5.5.1.	日交易参数



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/dayTradPara
请求方式
POST
请求Body参数
{
    "varietyId": "a",
    "tradeType": "1",
    "lang": "zh"
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
tradeType	1	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "e4385fb0-a8a8-4762-9734-3a2baab38785",
    "data": [
        {
            "contractId": "a2511",
            "specBuyRate": 0.07,
            "specBuy": 2770.6,
            "hedgeBuyRate": 0.07,
            "hedgeBuy": 2770.6,
            "riseLimitRate": 0.06,
            "riseLimit": 4195,
            "fallLimit": 3721,
            "style": "分开限仓",
            "selfTotBuyPosiQuota": 30000,
            "selfTotBuyPosiQuotaSerLimit": 30000,
            "clientBuyPosiQuota": 15000,
            "clientBuyPosiQuotaSerLimit": 15000,
            "contractLimit": null,
            "varietyLimit": null,
            "tradeDate": "20251013"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	e4385fb0-a8a8-4762-9734-3a2baab38785	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.contractId	a2511	string	合约
data.specBuyRate	0.07	number	比例-交易保证金(投机)
data.specBuy	2770.6	number	金额(元/手)-交易保证金(投机)
data.hedgeBuyRate	0.07	number	比例-交易保证金(套保)
data.hedgeBuy	2770.6	number	金额(元/手)-交易保证金(套保)
data.riseLimitRate	0.06	number	涨跌停板比例
data.riseLimit	4195	number	涨停板价位(元)
data.fallLimit	3721	number	跌停板价位(元)
data.style	分开限仓	string	限仓模式
data.selfTotBuyPosiQuota	30000	number	非期货公司会员-期货
data.selfTotBuyPosiQuotaSerLimit	30000	number	非期货公司会员-期权
data.clientBuyPosiQuota	15000	number	客户-持仓限额(手)-期货
data.clientBuyPosiQuotaSerLimit	15000	number	客户-持仓限额(手)-期权
data.contractLimit	-	null	合约限额
data.varietyLimit	-	null	品种限额
data.tradeDate	20251013	string	交易日

5.5.2.	月交易参数



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/monthTradPara
请求方式
POST
请求Body参数
{}
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "67b4c916-7150-41a3-bc55-268063bf0878",
    "data": {
        "monthDate": "2025年10月",
        "firstDate": "1009",
        "tenthDate": "1022",
        "fifteenthDate": "1029",
        "list": [
            {
                "varietyId": "b",
                "contractId": "b2510",
                "firstRate": 20,
                "fifteenthRate": 0,
                "firstRateHedge": 20,
                "fifteenthRateHedge": 0,
                "deliveryRiseLimit": 6,
                "firstSelfQuota": "           1,000",
                "firstClientQuota": "           1,000",
                "tenthSelfQuota": "           1,000",
                "tenthClientQuota": "           1,000"
            }
        ]
    }
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	67b4c916-7150-41a3-bc55-268063bf0878	string	-
data	-	object	用于承载API返回的具体数据内容，通常为JSON格式。
data.monthDate	2025年10月	string	-
data.firstDate	1009	string	本月第一个交易日
data.tenthDate	1022	string	本月第十个交易日
data.fifteenthDate	1029	string	本月第十五个交易日
data.list	-	array	-
data.list.varietyId	b	string	品种id
data.list.contractId	b2510	string	合约
data.list.firstRate	20	number	交易保证金(投机)-第一个交易日
data.list.fifteenthRate	0	number	交易保证金(投机)-第十五个交易日
data.list.firstRateHedge	20	number	交易保证金(套保)-第一个交易日
data.list.fifteenthRateHedge	0	number	交易保证金(套保)-第十五个交易日
data.list.deliveryRiseLimit	6	number	涨跌停板
data.list.firstSelfQuota	1,000	string	第一个交易日-非期货公司会员-持仓限额(手)
data.list.firstClientQuota	1,000	string	第一个交易日-客户-持仓限额(手)
data.list.tenthSelfQuota	1,000	string	第十个交易日-非期货公司会员-持仓限额(手)
data.list.tenthClientQuota	1,000	string	第十个交易日-客户-持仓限额(手)

5.5.3.	交易参数表（品种）



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/tradingParam
请求方式
POST
请求Body参数
{"lang":"zh"}
参数名	示例值	参数类型	是否必填	参数描述
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "61c3acef-acea-447b-a198-0113ded9e11a",
    "data": [
        {
            "varietyId": "a",
            "varietyName": "豆一",
            "tradingMarginRateSpeculation": "7%",
            "tradingMarginRateHedging": "7%",
            "priceLimitExistingContract": "6%",
            "priceLimitNewContract": "12%",
            "priceLimitDeliveryMonth": "6%",
            "tradingMarginRateSpeculationN": "7%",
            "tradingMarginRateHedgingN": "7%",
            "settlementMarginRateHedgingN": "11%",
            "priceLimitN": "6%",
            "tradingMarginRateN1": "11%",
            "settlementMarginRateHedgingN1": "13%",
            "priceLimitN1": "9%",
            "tradingMarginRateN2": "13%",
            "priceLimitN2": "11%",
            "tradingLimit": null,
            "specOpenFee": "2",
            "specOffsetFee": "2",
            "specShortOpenFee": "2",
            "specShortOffsetFee": "2",
            "hedgeOpenFee": "1",
            "hedgeOffsetFee": "1",
            "hedgeShortOpenFee": "1",
            "hedgeShortOffsetFee": "1",
            "feeStyle": "绝对值",
            "feeStyleEn": "absolute",
            "deliveryFee": "0.0",
            "maxHand": "1000"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	61c3acef-acea-447b-a198-0113ded9e11a	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.varietyId	a	string	品种id
data.varietyName	豆一	string	品种名称
data.tradingMarginRateSpeculation	7%	string	交易保证金（投机）
data.tradingMarginRateHedging	7%	string	交易保证金（套保）
data.priceLimitExistingContract	6%	string	已上市合约-涨跌停板幅度
data.priceLimitNewContract	12%	string	新上市合约-涨跌停板幅度
data.priceLimitDeliveryMonth	6%	string	交割月合约-涨跌停板幅度
data.tradingMarginRateSpeculationN	7%	string	交易时保证金（投机）-第N日
data.tradingMarginRateHedgingN	7%	string	交易时保证金（套保）-第N日
data.settlementMarginRateHedgingN	11%	string	结算时保证金（投机/套保）-第N日
data.priceLimitN	6%	string	涨跌停板幅度-第N日
data.tradingMarginRateN1	11%	string	交易时保证金（投机/套保）-第N+1日
data.settlementMarginRateHedgingN1	13%	string	结算时保证金（投机/套保）-第N+1日
data.priceLimitN1	9%	string	涨跌停板幅度-第N+1日
data.tradingMarginRateN2	13%	string	交易时保证金（投机/套保）-第N+2日
data.priceLimitN2	11%	string	涨跌停板幅度-第N+2日
data.tradingLimit	-	null	交易限额
data.specOpenFee	2	string	投机非日内开仓
data.specOffsetFee	2	string	投机非日内平仓
data.specShortOpenFee	2	string	投机日内开仓
data.specShortOffsetFee	2	string	投机日内平仓
data.hedgeOpenFee	1	string	套保非日内开仓
data.hedgeOffsetFee	1	string	套保非日内平仓
data.hedgeShortOpenFee	1	string	套保日内开仓
data.hedgeShortOffsetFee	1	string	套保日内平仓
data.feeStyle	绝对值	string	-
data.feeStyleEn	absolute	string	-
data.deliveryFee	0.0	string	交割手续费(元/手)
data.maxHand	1000	string	最大下单手数

5.5.4.	合约信息



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/contractInfo
请求方式
POST
请求Body参数
{"varietyId":"a","tradeType":"1","lang":"zh"}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
tradeType	1	string	是	固定值：1期货，2期权，0返回合集
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "31f69697-8de9-45f5-b928-2e41d1214935",
    "data": [
        {
            "contractId": "a2511",
            "variety": "豆一",
            "varietyOrder": "a",
            "unit": 10,
            "tick": "1",
            "startTradeDate": "20241115",
            "endTradeDate": "20251114",
            "endDeliveryDate": "20251119",
            "tradeType": "1"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	31f69697-8de9-45f5-b928-2e41d1214935	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.contractId	a2511	string	合约名称
data.variety	豆一	string	品种名称
data.varietyOrder	a	string	品种代码
data.unit	10	number	交易单位
data.tick	1	string	最小变动价位
data.startTradeDate	20241115	string	开始交易日
data.endTradeDate	20251114	string	最后交易日
data.endDeliveryDate	20251119	string	最后交割日
data.tradeType	1	string	交易类型

5.5.5.	套利合约明细



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/arbitrageContract
请求方式
POST
请求Body参数
{"lang":"zh"}
参数名	示例值	参数类型	是否必填	参数描述
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "2d858e98-c3ad-4787-b470-608f9cae769b",
    "data": [
        {
            "arbiName": "跨期套利",
            "varietyName": "豆一",
            "arbiContractId": "SP a2511&a2601",
            "maxHand": 1000,
            "tick": 1
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	2d858e98-c3ad-4787-b470-608f9cae769b	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.arbiName	跨期套利	string	套利交易策略
data.varietyName	豆一	string	品种名称
data.arbiContractId	SP a2511&a2601	string	套利交易合约
data.maxHand	1000	number	最大下单手数
data.tick	1	number	最小变动价位（元）

5.5.6.	套利交易保证金



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/marginArbiPerfPara
请求方式
POST
请求Body参数
{"lang":"zh"}
参数名	示例值	参数类型	是否必填	参数描述
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "44117cc2-4038-436c-9bc8-f0fc13231b84",
    "data": [
        {
            "arbiName": "跨期套利",
            "varietyName": "豆一",
            "arbiContractId": "SP a2511&a2601",
            "perfShType": "套保-套保",
            "marginAmt": 3536.1
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	44117cc2-4038-436c-9bc8-f0fc13231b84	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.arbiName	跨期套利	string	套利交易策略
data.varietyName	豆一	string	品种名称
data.arbiContractId	SP a2511&a2601	string	套利交易合约
data.perfShType	套保-套保	string	组合投机套保属性
data.marginAmt	3536.1	number	交易保证金额(手)

5.5.7.	期货/期权合约增挂



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/newContractInfo
请求方式
POST
请求Body参数
{"tradeDate":"20250716","tradeType":"2","lang":"zh"}
参数名	示例值	参数类型	是否必填	参数描述
tradeDate	20250716	string	是	交易日
tradeType	2	string	是	固定值：1期货，2期权
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "84cf89a5-1b03-415f-a427-199c93ad72b6",
    "data": [
        {
            "tradeType": "2",
            "variety": "玉米",
            "varietyOrder": "c",
            "contractId": "c2607-C-2040",
            "startTradeDate": "20250717",
            "refPriceUnit": "260元/吨",
            "noRiseLimit": null,
            "noFallLimit": null
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	84cf89a5-1b03-415f-a427-199c93ad72b6	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.tradeType	2	string	类型：1期货，2期权
data.variety	玉米	string	品种名称
data.varietyOrder	c	string	品种
data.contractId	c2607-C-2040	string	合约名称
data.startTradeDate	20250717	string	开始交易日
data.refPriceUnit	260元/吨	string	挂牌基准价
data.noRiseLimit	-	null	涨跌停板幅度
data.noFallLimit	-	null	-

5.5.8.	做市商持续报价合约



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/mainSeriesInfo
请求方式
POST
请求Body参数
{"varietyId":"a","tradeDate":"20251009"}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
tradeDate	20251009	string	是	交易日
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "381cf015-3bb3-4250-bfd4-80e6d13848c0",
    "data": [
        {
            "tradeDate": "20251009",
            "varietyId": "a",
            "seriesId": "a2511",
            "contractId": "a2511-C-3750"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	381cf015-3bb3-4250-bfd4-80e6d13848c0	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.tradeDate	20251009	string	交易日期
data.varietyId	a	string	期权品种
data.seriesId	a2511	string	期权系列
data.contractId	a2511-C-3750	string	做市商持续报价合约

5.6.	结算参数


5.6.1.	结算参数



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/tradepara/futAndOptSettle
请求方式
POST
请求Body参数
{"varietyId":"a","tradeDate":"20251009","tradeType":"1","lang":"zh"}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
tradeDate	20251009	string	是	交易日
tradeType	1	string	是	固定值：1期货，2期权。如传入其他值，则默认为1期货。
lang	zh	string	是	固定值：zh代表中文，en代表英文
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "b06053b3-8d22-4ecc-babe-64b0de458482",
    "data": [
        {
            "variety": "豆一",
            "varietyOrder": "a",
            "contractId": "a2511",
            "clearPrice": "3960",
            "openFee": "2",
            "offsetFee": "2",
            "shortOpenFee": "2",
            "shortOffsetFee": "2",
            "style": "绝对值",
            "specBuyRate": "0.07",
            "specSellRate": "0.07",
            "hedgeBuyRate": "0.07",
            "hedgeSellRate": "0.07",
            "hedgeOpenFee": "1",
            "hedgeOffsetFee": "1",
            "hedgeShortOpenFee": "1",
            "hedgeShortOffsetFee": "1"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	6bed383e-2b4f-4a3b-9687-568ed310f1d3	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.variety	豆一	string	品种名称
data.varietyOrder	a	string	品种代码
data.contractId	a2511	string	合约
data.clearPrice	3960	string	结算价
data.openFee	2	string	投机非日内开仓-手续费
data.offsetFee	2	string	投机非日内平仓-手续费
data.shortOpenFee	2	string	投机日内开仓-手续费
data.shortOffsetFee	2	string	投机日内平仓-手续费
data.style	绝对值	string	限仓模式
data.specBuyRate	0.07	string	投机买-保证金率
data.specSellRate	0.07	string	投机卖-保证金率
data.hedgeBuyRate	0.07	string	套保买-保证金率
data.hedgeSellRate	0.07	string	套保卖-保证金率
data.hedgeOpenFee	1	string	套保非日内开仓-手续费
data.hedgeOffsetFee	1	string	套保非日内平仓-手续费
data.hedgeShortOpenFee	1	string	套保日内开仓-手续费
data.hedgeShortOffsetFee	1	string	套保日内平仓-手续费

5.7.	交割参数


5.7.1.	交割费用标准



接口URL
http://www.dce.com.cn/dceapi/forward/publicweb/deliverypara/deliveryCosts
请求方式
POST
请求Body参数
{
    "varietyId": "a",
"varietyType": "1",
    "lang": "zh"
}
参数名	示例值	参数类型	是否必填	参数描述
varietyId	a	string	是	品种id，全部为all
lang	zh	string	是	固定值：zh代表中文，en代表英文
varietyType	1	string	是	0,实物交割费用标准;1,月均价交割费用标准
响应示例
•	成功(200)
{
    "success": true,
    "code": 200,
    "msg": "操作成功",
    "requestId": "b87c9829-61a1-48ff-8fb4-084b46952643",
    "data": [
        {
            "variety": "豆一",
            "earnestRate": "10",
            "unit": "吨",
            "deliveryFee": "0",
            "feeRate": "4",
            "startDate": "0101",
            "endDate": "0430"
        }
    ]
}
参数名	示例值	参数类型	参数描述
success	true	boolean	-
code	200	number	-
msg	操作成功	string	-
requestId	b87c9829-61a1-48ff-8fb4-084b46952643	string	-
data	-	array	用于承载API返回的具体数据内容，通常为JSON格式。
data.variety	豆一	string	品种名称
data.earnestRate	10	string	交割预报定金率(元/最小单位)
data.unit	吨	string	交易单位
data.deliveryFee	0	string	交割手续费(元/手)
data.feeRate	4	string	仓储费标准(元/手天)
data.startDate	0101	string	开始日期
data.endDate	0430	string	结束日期

